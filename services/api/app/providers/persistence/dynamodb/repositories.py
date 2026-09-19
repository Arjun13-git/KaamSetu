"""DynamoDB implementation of the persistence ports (see ``domain/repositories.py``).

Multi-record writes use ``TransactWriteItems`` so they are all-or-nothing. Concurrency control is
optimistic: mutable records carry a ``version`` checked by a condition expression. Failures of the
store are logged with the AWS error code only and surface as a generic ``StorageError``.
"""

import logging
from collections.abc import Iterable
from typing import Any

from boto3.dynamodb.conditions import Attr, ConditionBase, Key
from botocore.exceptions import BotoCoreError, ClientError

from app.core.errors import ConflictError, DuplicateRequestError, NotFoundError, StorageError
from app.domain.asset import Asset
from app.domain.audit import AuditEvent
from app.domain.base import DomainModel
from app.domain.business import Business
from app.domain.customer import Customer
from app.domain.enums import AuditEntityType, JobStatus, ServiceRequestStatus
from app.domain.job import Job
from app.domain.normalization import normalize_name, normalize_phone, normalize_serial
from app.domain.repositories import (
    DEFAULT_LIMIT,
    Repositories,
    ensure_completion_consistent,
    ensure_creatable_job,
    ensure_request_link,
    ensure_updatable_job,
    ensure_updatable_request,
)
from app.domain.service_event import ServiceEvent
from app.domain.service_request import ServiceRequest
from app.domain.technician import Technician
from app.providers.persistence.dynamodb import keys
from app.providers.persistence.dynamodb.serde import from_item, to_item

logger = logging.getLogger(__name__)

_TERMINAL_JOB = (JobStatus.COMPLETED.value, JobStatus.CANCELLED.value)
_CLOSED_REQUEST = (ServiceRequestStatus.JOB_CREATED.value, ServiceRequestStatus.DISMISSED.value)


class _Cancelled(Exception):
    """A transaction was cancelled; ``reasons`` lines up with the submitted items."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("transaction cancelled")
        self.reasons = reasons

    def failed(self, index: int) -> bool:
        return index < len(self.reasons) and self.reasons[index] == "ConditionalCheckFailed"


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


class DynamoStore:
    """Thin, tenant-agnostic access layer over one table. Every AWS call goes through here so
    error translation and logging live in one place."""

    def __init__(self, resource: Any, table_name: str) -> None:
        self._table = resource.Table(table_name)
        self._client = resource.meta.client
        self._table_name = table_name

    # -- reads ---------------------------------------------------------------------------

    def get[T: DomainModel](self, item_keys: keys.Keys, model_type: type[T], kind: str) -> T:
        item = self.get_raw(item_keys)
        if item is None:
            raise NotFoundError(f"{kind} not found")
        return from_item(item, model_type)

    def get_raw(self, item_keys: keys.Keys) -> dict[str, Any] | None:
        try:
            response = self._table.get_item(Key=item_keys, ConsistentRead=True)
        except (ClientError, BotoCoreError) as exc:
            raise self._storage_error(exc) from exc
        item = response.get("Item")
        return item if isinstance(item, dict) else None

    def query[T: DomainModel](
        self,
        model_type: type[T],
        pk_value: str,
        *,
        index: str | None = None,
        sk_prefix: str | None = None,
        item_filter: ConditionBase | None = None,
        newest_first: bool = False,
        limit: int | None = None,
    ) -> list[T]:
        """Query one partition (of the base table or a GSI), following pagination.

        ``limit`` is applied by DynamoDB only when there is no filter; otherwise every match is
        read and the caller trims after sorting.
        """
        pk_attr, sk_attr = (f"{index}PK", f"{index}SK") if index else ("PK", "SK")
        condition = Key(pk_attr).eq(pk_value)
        if sk_prefix is not None:
            condition = condition & Key(sk_attr).begins_with(sk_prefix)
        request: dict[str, Any] = {
            "KeyConditionExpression": condition,
            "ScanIndexForward": not newest_first,
        }
        if index:
            request["IndexName"] = index
        else:
            request["ConsistentRead"] = True
        if item_filter is not None:
            request["FilterExpression"] = item_filter
        native_limit = limit if item_filter is None else None

        found: list[T] = []
        try:
            while True:
                if native_limit is not None:
                    request["Limit"] = native_limit - len(found)
                page = self._table.query(**request)
                found.extend(from_item(item, model_type) for item in page.get("Items", []))
                last_key = page.get("LastEvaluatedKey")
                if not last_key or (native_limit is not None and len(found) >= native_limit):
                    return found
                request["ExclusiveStartKey"] = last_key
        except (ClientError, BotoCoreError) as exc:
            raise self._storage_error(exc) from exc

    # -- writes --------------------------------------------------------------------------

    def put_new(self, item: dict[str, Any], kind: str) -> None:
        if not self.try_put(item):
            raise ConflictError(f"{kind} already exists")

    def try_put(self, item: dict[str, Any], condition: dict[str, Any] | None = None) -> bool:
        """Conditional put. Returns ``False`` if the condition failed, ``True`` if written."""
        guard = condition or {"ConditionExpression": "attribute_not_exists(PK)"}
        try:
            self._table.put_item(Item=item, **guard)
        except ClientError as exc:
            if _error_code(exc) == "ConditionalCheckFailedException":
                return False
            raise self._storage_error(exc) from exc
        except BotoCoreError as exc:
            raise self._storage_error(exc) from exc
        return True

    def put_op(
        self, item: dict[str, Any], condition: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        guard = condition or {"ConditionExpression": "attribute_not_exists(PK)"}
        return {"Put": {"TableName": self._table_name, "Item": item, **guard}}

    def transact(self, operations: list[dict[str, Any]]) -> None:
        """All-or-nothing. Raises ``_Cancelled`` when a condition fails."""
        try:
            self._client.transact_write_items(TransactItems=operations)
        except ClientError as exc:
            if _error_code(exc) == "TransactionCanceledException":
                reasons = [
                    str(r.get("Code", "None")) for r in exc.response.get("CancellationReasons", [])
                ]
                raise _Cancelled(reasons) from exc
            raise self._storage_error(exc) from exc
        except BotoCoreError as exc:
            raise self._storage_error(exc) from exc

    @staticmethod
    def _storage_error(exc: Exception) -> StorageError:
        code = _error_code(exc) if isinstance(exc, ClientError) else type(exc).__name__
        logger.error("DynamoDB operation failed: %s", code)
        return StorageError("The data store could not complete the request")


def _versioned(
    expected_version: int, *, forbid: Iterable[str] = (), require: str | None = None
) -> dict[str, Any]:
    """Condition: the item exists at ``expected_version`` and its status is acceptable."""
    names = {"#v": "version", "#s": "status"}
    values: dict[str, Any] = {":ev": expected_version}
    clauses = ["attribute_exists(PK)", "#v = :ev"]
    if require is not None:
        clauses.append("#s = :required")
        values[":required"] = require
    for index, status in enumerate(forbid):
        clauses.append(f"#s <> :forbidden{index}")
        values[f":forbidden{index}"] = status
    return {
        "ConditionExpression": " AND ".join(clauses),
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
    }


def _by_name[T: Customer | Technician](items: list[T], id_field: str) -> list[T]:
    return sorted(items, key=lambda i: (normalize_name(i.name), getattr(i, id_field)))


def _newest_first[T: DomainModel](items: list[T], time_field: str, id_field: str) -> list[T]:
    return sorted(items, key=lambda i: (getattr(i, time_field), getattr(i, id_field)), reverse=True)


class DynamoBusinessRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    def create(self, business: Business) -> None:
        item = to_item(business, keys.business_keys(business.business_id), "BUSINESS")
        self._s.put_new(item, "Business")

    def get(self, business_id: str) -> Business:
        return self._s.get(keys.business_keys(business_id), Business, "Business")


class DynamoCustomerRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    def create(self, customer: Customer) -> None:
        item = to_item(
            customer,
            keys.customer_keys(customer),
            "CUSTOMER",
            {"name_search": normalize_name(customer.name)},
        )
        self._s.put_new(item, "Customer")

    def get(self, business_id: str, customer_id: str) -> Customer:
        item_keys = keys.base_keys(business_id, keys.CUSTOMER, customer_id)
        return self._s.get(item_keys, Customer, "Customer")

    def list(self, business_id: str, *, limit: int = DEFAULT_LIMIT) -> list[Customer]:
        customers = self._s.query(Customer, keys.tenant(business_id), sk_prefix=f"{keys.CUSTOMER}#")
        return _by_name(customers, "customer_id")[:limit]

    def find_by_phone(self, business_id: str, phone: str) -> list[Customer]:
        normalized = normalize_phone(phone)
        if normalized is None:
            return []
        customers = self._s.query(
            Customer,
            keys.phone_partition(business_id, normalized),
            index=keys.GSI1,
            sk_prefix=f"{keys.CUSTOMER}#",
        )
        return _by_name(customers, "customer_id")

    def search_by_name(
        self, business_id: str, query: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Customer]:
        needle = normalize_name(query)
        if not needle:
            return []
        customers = self._s.query(
            Customer,
            keys.tenant(business_id),
            sk_prefix=f"{keys.CUSTOMER}#",
            item_filter=Attr("name_search").contains(needle),
        )
        return _by_name(customers, "customer_id")[:limit]


class DynamoAssetRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    def create(self, asset: Asset) -> None:
        self._s.put_new(to_item(asset, keys.asset_keys(asset), "ASSET"), "Asset")

    def get(self, business_id: str, asset_id: str) -> Asset:
        return self._s.get(keys.base_keys(business_id, keys.ASSET, asset_id), Asset, "Asset")

    def list_by_customer(self, business_id: str, customer_id: str) -> list[Asset]:
        assets = self._s.query(
            Asset,
            keys.customer_partition(business_id, customer_id),
            index=keys.GSI2,
            sk_prefix=f"{keys.ASSET}#",
        )
        return sorted(assets, key=lambda a: (a.created_at, a.asset_id))

    def find_by_serial(self, business_id: str, serial_number: str) -> list[Asset]:
        needle = normalize_serial(serial_number)
        if not needle:
            return []
        assets = self._s.query(
            Asset,
            keys.serial_partition(business_id, needle),
            index=keys.GSI1,
            sk_prefix=f"{keys.ASSET}#",
        )
        return sorted(assets, key=lambda a: (a.created_at, a.asset_id))


class DynamoTechnicianRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    def create(self, technician: Technician) -> None:
        item = to_item(
            technician,
            keys.base_keys(technician.business_id, keys.TECHNICIAN, technician.technician_id),
            "TECHNICIAN",
        )
        self._s.put_new(item, "Technician")

    def get(self, business_id: str, technician_id: str) -> Technician:
        item_keys = keys.base_keys(business_id, keys.TECHNICIAN, technician_id)
        return self._s.get(item_keys, Technician, "Technician")

    def list(self, business_id: str, *, active_only: bool = False) -> list[Technician]:
        technicians = self._s.query(
            Technician,
            keys.tenant(business_id),
            sk_prefix=f"{keys.TECHNICIAN}#",
            item_filter=Attr("active").eq(True) if active_only else None,
        )
        return _by_name(technicians, "technician_id")


class DynamoServiceRequestRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    def _item(self, request: ServiceRequest) -> dict[str, Any]:
        item_keys = keys.base_keys(
            request.business_id, keys.SERVICE_REQUEST, request.service_request_id
        )
        return to_item(request, item_keys, "SERVICE_REQUEST")

    def create(self, request: ServiceRequest) -> None:
        if request.idempotency_key is None:
            self._s.put_new(self._item(request), "Service request")
            return
        reservation = {
            **keys.idempotency_keys(request.business_id, request.idempotency_key),
            "item_type": "IDEMPOTENCY",
            "service_request_id": request.service_request_id,
        }
        try:
            self._s.transact([self._s.put_op(self._item(request)), self._s.put_op(reservation)])
        except _Cancelled as cancelled:
            if cancelled.failed(1):
                raise DuplicateRequestError("This idempotency key was already used") from None
            raise ConflictError("Service request already exists") from None

    def get(self, business_id: str, service_request_id: str) -> ServiceRequest:
        item_keys = keys.base_keys(business_id, keys.SERVICE_REQUEST, service_request_id)
        return self._s.get(item_keys, ServiceRequest, "Service request")

    def get_by_idempotency_key(self, business_id: str, key: str) -> ServiceRequest | None:
        reservation = self._s.get_raw(keys.idempotency_keys(business_id, key))
        if reservation is None:
            return None
        return self.get(business_id, str(reservation["service_request_id"]))

    def update(self, request: ServiceRequest) -> None:
        ensure_updatable_request(request)
        condition = _versioned(request.version - 1, forbid=_CLOSED_REQUEST)
        if self._s.try_put(self._item(request), condition):
            return
        self.get(request.business_id, request.service_request_id)  # NotFoundError if absent
        raise ConflictError("The service request was modified concurrently or is closed")

    def list(
        self,
        business_id: str,
        *,
        status: ServiceRequestStatus | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[ServiceRequest]:
        requests = self._s.query(
            ServiceRequest,
            keys.tenant(business_id),
            sk_prefix=f"{keys.SERVICE_REQUEST}#",
            item_filter=Attr("status").eq(status.value) if status else None,
        )
        return _newest_first(requests, "created_at", "service_request_id")[:limit]


class DynamoJobRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    @staticmethod
    def _item(job: Job) -> dict[str, Any]:
        return to_item(job, keys.job_keys(job), "JOB")

    @staticmethod
    def _audit_item(audit: AuditEvent) -> dict[str, Any]:
        return to_item(audit, keys.audit_keys(audit), "AUDIT")

    def create(self, job: Job, audit: AuditEvent) -> None:
        ensure_creatable_job(job)
        try:
            self._s.transact(
                [
                    self._s.put_op(self._item(job)),
                    self._s.put_op(self._audit_item(audit)),
                ]
            )
        except _Cancelled as cancelled:
            what = "Job" if cancelled.failed(0) else "Audit event"
            raise ConflictError(f"{what} already exists") from None

    def create_for_request(self, job: Job, request: ServiceRequest, audit: AuditEvent) -> None:
        ensure_creatable_job(job)
        ensure_request_link(job, request)
        request_item = to_item(
            request,
            keys.base_keys(request.business_id, keys.SERVICE_REQUEST, request.service_request_id),
            "SERVICE_REQUEST",
        )
        try:
            self._s.transact(
                [
                    self._s.put_op(self._item(job)),
                    self._s.put_op(
                        request_item, _versioned(request.version - 1, forbid=_CLOSED_REQUEST)
                    ),
                    self._s.put_op(self._audit_item(audit)),
                ]
            )
        except _Cancelled as cancelled:
            if cancelled.failed(1):
                # NotFoundError if the request is absent, otherwise it is stale or closed.
                self._s.get(
                    keys.base_keys(
                        request.business_id, keys.SERVICE_REQUEST, request.service_request_id
                    ),
                    ServiceRequest,
                    "Service request",
                )
                raise ConflictError(
                    "The service request was modified concurrently or already has a job"
                ) from None
            raise ConflictError("The job or its audit record already exists") from None

    def get(self, business_id: str, job_id: str) -> Job:
        return self._s.get(keys.base_keys(business_id, keys.JOB, job_id), Job, "Job")

    def update(self, job: Job, audit: AuditEvent) -> None:
        ensure_updatable_job(job)
        try:
            self._s.transact(
                [
                    self._s.put_op(
                        self._item(job), _versioned(job.version - 1, forbid=_TERMINAL_JOB)
                    ),
                    self._s.put_op(self._audit_item(audit)),
                ]
            )
        except _Cancelled as cancelled:
            if cancelled.failed(0):
                self.get(job.business_id, job.job_id)  # NotFoundError if absent
                raise ConflictError("The job was modified concurrently or is closed") from None
            raise ConflictError("Audit event already exists") from None

    def complete(self, job: Job, event: ServiceEvent, audit: AuditEvent) -> None:
        ensure_completion_consistent(job, event, audit)
        in_progress = JobStatus.IN_PROGRESS.value
        try:
            self._s.transact(
                [
                    self._s.put_op(
                        self._item(job), _versioned(job.version - 1, require=in_progress)
                    ),
                    self._s.put_op(to_item(event, keys.event_keys(event), "EVENT")),
                    self._s.put_op(self._audit_item(audit)),
                ]
            )
        except _Cancelled as cancelled:
            if cancelled.failed(0):
                self.get(job.business_id, job.job_id)  # NotFoundError if absent
                raise ConflictError(
                    "The job was modified concurrently or is not IN_PROGRESS"
                ) from None
            raise ConflictError("The service event or audit record already exists") from None

    def list(
        self,
        business_id: str,
        *,
        status: JobStatus | None = None,
        technician_id: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[Job]:
        item_filter: ConditionBase | None = None
        for attribute, value in (
            ("status", status.value if status else None),
            ("technician_id", technician_id),
        ):
            if value is not None:
                clause = Attr(attribute).eq(value)
                item_filter = clause if item_filter is None else item_filter & clause
        jobs = self._s.query(
            Job, keys.tenant(business_id), sk_prefix=f"{keys.JOB}#", item_filter=item_filter
        )
        return _newest_first(jobs, "created_at", "job_id")[:limit]

    def list_by_customer(
        self, business_id: str, customer_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Job]:
        return self._s.query(
            Job,
            keys.customer_partition(business_id, customer_id),
            index=keys.GSI2,
            sk_prefix=f"{keys.JOB}#",
            newest_first=True,
            limit=limit,
        )

    def list_by_asset(
        self, business_id: str, asset_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Job]:
        return self._s.query(
            Job,
            keys.asset_partition(business_id, asset_id),
            index=keys.GSI3,
            sk_prefix=f"{keys.JOB}#",
            newest_first=True,
            limit=limit,
        )


class DynamoServiceEventRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    def get(self, business_id: str, event_id: str) -> ServiceEvent:
        item_keys = keys.base_keys(business_id, keys.EVENT, event_id)
        return self._s.get(item_keys, ServiceEvent, "Service event")

    def list_by_asset(
        self, business_id: str, asset_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[ServiceEvent]:
        return self._s.query(
            ServiceEvent,
            keys.asset_partition(business_id, asset_id),
            index=keys.GSI3,
            sk_prefix=f"{keys.EVENT}#",
            newest_first=True,
            limit=limit,
        )

    def list_by_customer(
        self, business_id: str, customer_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[ServiceEvent]:
        return self._s.query(
            ServiceEvent,
            keys.customer_partition(business_id, customer_id),
            index=keys.GSI2,
            sk_prefix=f"{keys.EVENT}#",
            newest_first=True,
            limit=limit,
        )


class DynamoAuditRepository:
    def __init__(self, store: DynamoStore) -> None:
        self._s = store

    def append(self, audit: AuditEvent) -> None:
        self._s.put_new(to_item(audit, keys.audit_keys(audit), "AUDIT"), "Audit event")

    def list_for_entity(
        self, business_id: str, entity_type: AuditEntityType, entity_id: str
    ) -> list[AuditEvent]:
        return self._s.query(
            AuditEvent,
            keys.audit_partition(business_id, entity_type.value, entity_id),
            index=keys.GSI2,
        )


def build_dynamodb_repositories(resource: Any, table_name: str) -> Repositories:
    store = DynamoStore(resource, table_name)
    return Repositories(
        businesses=DynamoBusinessRepository(store),
        customers=DynamoCustomerRepository(store),
        assets=DynamoAssetRepository(store),
        technicians=DynamoTechnicianRepository(store),
        service_requests=DynamoServiceRequestRepository(store),
        jobs=DynamoJobRepository(store),
        service_events=DynamoServiceEventRepository(store),
        audits=DynamoAuditRepository(store),
    )
