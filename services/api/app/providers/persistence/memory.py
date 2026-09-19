"""In-memory repositories: the reference implementation of the persistence ports.

Used for unit tests, local development without infrastructure and as the behavioural baseline the
DynamoDB adapter must match. Records are deep-copied on the way in and out so callers can never
alias stored state. All multi-record writes hold one lock and validate before mutating, giving the
same all-or-nothing behaviour the DynamoDB adapter gets from transactions.
"""

from dataclasses import dataclass, field
from threading import RLock

from app.core.errors import ConflictError, DuplicateRequestError, NotFoundError
from app.domain.asset import Asset
from app.domain.audit import AuditEvent
from app.domain.base import DomainModel
from app.domain.business import Business
from app.domain.customer import Customer
from app.domain.enums import AuditEntityType, JobStatus, ServiceRequestStatus
from app.domain.job import Job
from app.domain.job_state_machine import TERMINAL_STATUSES
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

_CLOSED_REQUEST_STATUSES = frozenset(
    {ServiceRequestStatus.JOB_CREATED, ServiceRequestStatus.DISMISSED}
)


@dataclass
class InMemoryStore:
    lock: RLock = field(default_factory=RLock)
    businesses: dict[tuple[str, str], Business] = field(default_factory=dict)
    customers: dict[tuple[str, str], Customer] = field(default_factory=dict)
    assets: dict[tuple[str, str], Asset] = field(default_factory=dict)
    technicians: dict[tuple[str, str], Technician] = field(default_factory=dict)
    service_requests: dict[tuple[str, str], ServiceRequest] = field(default_factory=dict)
    idempotency: dict[tuple[str, str], str] = field(default_factory=dict)
    jobs: dict[tuple[str, str], Job] = field(default_factory=dict)
    events: dict[tuple[str, str], ServiceEvent] = field(default_factory=dict)
    audits: dict[tuple[str, str], AuditEvent] = field(default_factory=dict)


def _copy[T: DomainModel](model: T) -> T:
    return model.model_copy(deep=True)


def _fetch[T: DomainModel](
    table: dict[tuple[str, str], T], business_id: str, entity_id: str, kind: str
) -> T:
    try:
        return _copy(table[(business_id, entity_id)])
    except KeyError:
        raise NotFoundError(f"{kind} not found") from None


def _check_new(
    table: dict[tuple[str, str], object], business_id: str, entity_id: str, kind: str
) -> None:
    if (business_id, entity_id) in table:
        raise ConflictError(f"{kind} already exists")


def _in_business[T: DomainModel](table: dict[tuple[str, str], T], business_id: str) -> list[T]:
    return [_copy(item) for (owner, _), item in table.items() if owner == business_id]


def _newest_first[T: DomainModel](items: list[T], time_field: str, id_field: str) -> list[T]:
    return sorted(items, key=lambda i: (getattr(i, time_field), getattr(i, id_field)), reverse=True)


class InMemoryBusinessRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def create(self, business: Business) -> None:
        with self._s.lock:
            _check_new(self._s.businesses, business.business_id, business.business_id, "Business")
            self._s.businesses[(business.business_id, business.business_id)] = _copy(business)

    def get(self, business_id: str) -> Business:
        with self._s.lock:
            return _fetch(self._s.businesses, business_id, business_id, "Business")


class InMemoryCustomerRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def create(self, customer: Customer) -> None:
        with self._s.lock:
            key = (customer.business_id, customer.customer_id)
            _check_new(self._s.customers, *key, "Customer")
            self._s.customers[key] = _copy(customer)

    def get(self, business_id: str, customer_id: str) -> Customer:
        with self._s.lock:
            return _fetch(self._s.customers, business_id, customer_id, "Customer")

    def list(self, business_id: str, *, limit: int = DEFAULT_LIMIT) -> list[Customer]:
        with self._s.lock:
            return _by_name(_in_business(self._s.customers, business_id), "customer_id")[:limit]

    def find_by_phone(self, business_id: str, phone: str) -> list[Customer]:
        normalized = normalize_phone(phone)
        if normalized is None:
            return []
        with self._s.lock:
            matches = [
                c for c in _in_business(self._s.customers, business_id) if c.phone == normalized
            ]
        return _by_name(matches, "customer_id")

    def search_by_name(
        self, business_id: str, query: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Customer]:
        needle = normalize_name(query)
        if not needle:
            return []
        with self._s.lock:
            candidates = _in_business(self._s.customers, business_id)
        return _by_name([c for c in candidates if needle in normalize_name(c.name)], "customer_id")[
            :limit
        ]


def _by_name[T: Customer | Technician](items: list[T], id_field: str) -> list[T]:
    return sorted(items, key=lambda i: (normalize_name(i.name), getattr(i, id_field)))


class InMemoryAssetRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def create(self, asset: Asset) -> None:
        with self._s.lock:
            key = (asset.business_id, asset.asset_id)
            _check_new(self._s.assets, *key, "Asset")
            self._s.assets[key] = _copy(asset)

    def get(self, business_id: str, asset_id: str) -> Asset:
        with self._s.lock:
            return _fetch(self._s.assets, business_id, asset_id, "Asset")

    def list_by_customer(self, business_id: str, customer_id: str) -> list[Asset]:
        with self._s.lock:
            owned = [
                a for a in _in_business(self._s.assets, business_id) if a.customer_id == customer_id
            ]
        return sorted(owned, key=lambda a: (a.created_at, a.asset_id))

    def find_by_serial(self, business_id: str, serial_number: str) -> list[Asset]:
        needle = normalize_serial(serial_number)
        if not needle:
            return []
        with self._s.lock:
            assets = _in_business(self._s.assets, business_id)
        matches = [
            a for a in assets if a.serial_number and normalize_serial(a.serial_number) == needle
        ]
        return sorted(matches, key=lambda a: (a.created_at, a.asset_id))


class InMemoryTechnicianRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def create(self, technician: Technician) -> None:
        with self._s.lock:
            key = (technician.business_id, technician.technician_id)
            _check_new(self._s.technicians, *key, "Technician")
            self._s.technicians[key] = _copy(technician)

    def get(self, business_id: str, technician_id: str) -> Technician:
        with self._s.lock:
            return _fetch(self._s.technicians, business_id, technician_id, "Technician")

    def list(self, business_id: str, *, active_only: bool = False) -> list[Technician]:
        with self._s.lock:
            technicians = _in_business(self._s.technicians, business_id)
        return _by_name([t for t in technicians if t.active or not active_only], "technician_id")


class InMemoryServiceRequestRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def create(self, request: ServiceRequest) -> None:
        with self._s.lock:
            key = (request.business_id, request.service_request_id)
            _check_new(self._s.service_requests, *key, "Service request")
            if request.idempotency_key is not None:
                idem_key = (request.business_id, request.idempotency_key)
                if idem_key in self._s.idempotency:
                    raise DuplicateRequestError("This idempotency key was already used")
                self._s.idempotency[idem_key] = request.service_request_id
            self._s.service_requests[key] = _copy(request)

    def get(self, business_id: str, service_request_id: str) -> ServiceRequest:
        with self._s.lock:
            return _fetch(
                self._s.service_requests, business_id, service_request_id, "Service request"
            )

    def get_by_idempotency_key(self, business_id: str, key: str) -> ServiceRequest | None:
        with self._s.lock:
            request_id = self._s.idempotency.get((business_id, key))
            if request_id is None:
                return None
            return _fetch(self._s.service_requests, business_id, request_id, "Service request")

    def update(self, request: ServiceRequest) -> None:
        ensure_updatable_request(request)
        with self._s.lock:
            stored = _fetch(
                self._s.service_requests,
                request.business_id,
                request.service_request_id,
                "Service request",
            )
            if stored.status in _CLOSED_REQUEST_STATUSES:
                raise ConflictError(f"A {stored.status.value} service request cannot be changed")
            if stored.version != request.version - 1:
                raise ConflictError("The service request was modified concurrently")
            self._s.service_requests[(request.business_id, request.service_request_id)] = _copy(
                request
            )

    def list(
        self,
        business_id: str,
        *,
        status: ServiceRequestStatus | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[ServiceRequest]:
        with self._s.lock:
            requests = _in_business(self._s.service_requests, business_id)
        matching = [r for r in requests if status is None or r.status is status]
        return _newest_first(matching, "created_at", "service_request_id")[:limit]


class InMemoryJobRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def create(self, job: Job, audit: AuditEvent) -> None:
        ensure_creatable_job(job)
        with self._s.lock:
            _check_new(self._s.jobs, job.business_id, job.job_id, "Job")
            _check_new(self._s.audits, audit.business_id, audit.audit_id, "Audit event")
            self._s.jobs[(job.business_id, job.job_id)] = _copy(job)
            self._s.audits[(audit.business_id, audit.audit_id)] = _copy(audit)

    def create_for_request(self, job: Job, request: ServiceRequest, audit: AuditEvent) -> None:
        ensure_creatable_job(job)
        ensure_request_link(job, request)
        with self._s.lock:
            stored = _fetch(
                self._s.service_requests,
                request.business_id,
                request.service_request_id,
                "Service request",
            )
            if stored.status in _CLOSED_REQUEST_STATUSES:
                raise ConflictError(f"A {stored.status.value} service request cannot start a job")
            if stored.version != request.version - 1:
                raise ConflictError("The service request was modified concurrently")
            _check_new(self._s.jobs, job.business_id, job.job_id, "Job")
            _check_new(self._s.audits, audit.business_id, audit.audit_id, "Audit event")
            self._s.jobs[(job.business_id, job.job_id)] = _copy(job)
            self._s.service_requests[(request.business_id, request.service_request_id)] = _copy(
                request
            )
            self._s.audits[(audit.business_id, audit.audit_id)] = _copy(audit)

    def get(self, business_id: str, job_id: str) -> Job:
        with self._s.lock:
            return _fetch(self._s.jobs, business_id, job_id, "Job")

    def update(self, job: Job, audit: AuditEvent) -> None:
        ensure_updatable_job(job)
        with self._s.lock:
            stored = _fetch(self._s.jobs, job.business_id, job.job_id, "Job")
            if stored.status in TERMINAL_STATUSES:
                raise ConflictError(f"A {stored.status.value} job can no longer be changed")
            if stored.version != job.version - 1:
                raise ConflictError("The job was modified concurrently")
            _check_new(self._s.audits, audit.business_id, audit.audit_id, "Audit event")
            self._s.jobs[(job.business_id, job.job_id)] = _copy(job)
            self._s.audits[(audit.business_id, audit.audit_id)] = _copy(audit)

    def complete(self, job: Job, event: ServiceEvent, audit: AuditEvent) -> None:
        ensure_completion_consistent(job, event, audit)
        with self._s.lock:
            stored = _fetch(self._s.jobs, job.business_id, job.job_id, "Job")
            if stored.status is not JobStatus.IN_PROGRESS:
                raise ConflictError(f"A {stored.status.value} job cannot be completed")
            if stored.version != job.version - 1:
                raise ConflictError("The job was modified concurrently")
            _check_new(self._s.events, event.business_id, event.event_id, "Service event")
            _check_new(self._s.audits, audit.business_id, audit.audit_id, "Audit event")
            self._s.jobs[(job.business_id, job.job_id)] = _copy(job)
            self._s.events[(event.business_id, event.event_id)] = _copy(event)
            self._s.audits[(audit.business_id, audit.audit_id)] = _copy(audit)

    def list(
        self,
        business_id: str,
        *,
        status: JobStatus | None = None,
        technician_id: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[Job]:
        with self._s.lock:
            jobs = _in_business(self._s.jobs, business_id)
        matching = [
            j
            for j in jobs
            if (status is None or j.status is status)
            and (technician_id is None or j.technician_id == technician_id)
        ]
        return _newest_first(matching, "created_at", "job_id")[:limit]

    def list_by_customer(
        self, business_id: str, customer_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Job]:
        with self._s.lock:
            jobs = _in_business(self._s.jobs, business_id)
        owned = [j for j in jobs if j.customer_id == customer_id]
        return _newest_first(owned, "created_at", "job_id")[:limit]

    def list_by_asset(
        self, business_id: str, asset_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Job]:
        with self._s.lock:
            jobs = _in_business(self._s.jobs, business_id)
        owned = [j for j in jobs if j.asset_id == asset_id]
        return _newest_first(owned, "created_at", "job_id")[:limit]


class InMemoryServiceEventRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def get(self, business_id: str, event_id: str) -> ServiceEvent:
        with self._s.lock:
            return _fetch(self._s.events, business_id, event_id, "Service event")

    def list_by_asset(
        self, business_id: str, asset_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[ServiceEvent]:
        with self._s.lock:
            events = _in_business(self._s.events, business_id)
        return _newest_first(
            [e for e in events if e.asset_id == asset_id], "timestamp", "event_id"
        )[:limit]

    def list_by_customer(
        self, business_id: str, customer_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[ServiceEvent]:
        with self._s.lock:
            events = _in_business(self._s.events, business_id)
        owned = [e for e in events if e.customer_id == customer_id]
        return _newest_first(owned, "timestamp", "event_id")[:limit]


class InMemoryAuditRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._s = store

    def append(self, audit: AuditEvent) -> None:
        with self._s.lock:
            _check_new(self._s.audits, audit.business_id, audit.audit_id, "Audit event")
            self._s.audits[(audit.business_id, audit.audit_id)] = _copy(audit)

    def list_for_entity(
        self, business_id: str, entity_type: AuditEntityType, entity_id: str
    ) -> list[AuditEvent]:
        with self._s.lock:
            audits = _in_business(self._s.audits, business_id)
        matching = [a for a in audits if a.entity_type is entity_type and a.entity_id == entity_id]
        return sorted(matching, key=lambda a: (a.timestamp, a.audit_id))


def build_in_memory_repositories(store: InMemoryStore | None = None) -> Repositories:
    shared = store or InMemoryStore()
    return Repositories(
        businesses=InMemoryBusinessRepository(shared),
        customers=InMemoryCustomerRepository(shared),
        assets=InMemoryAssetRepository(shared),
        technicians=InMemoryTechnicianRepository(shared),
        service_requests=InMemoryServiceRequestRepository(shared),
        jobs=InMemoryJobRepository(shared),
        service_events=InMemoryServiceEventRepository(shared),
        audits=InMemoryAuditRepository(shared),
    )
