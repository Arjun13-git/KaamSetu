"""Persistence ports. The domain depends on these interfaces, never on a storage vendor.

Every method is tenant scoped: reads take ``business_id`` and treat a record owned by another
business exactly like a missing one (``NotFoundError``); writes derive the tenant from the record.

Error contract shared by all adapters:
- ``NotFoundError``: the record does not exist in that business.
- ``ConflictError``: the record already exists, a version check failed, or a state guard failed.
- ``DuplicateRequestError``: an idempotency key was already used within the business.
- ``StorageError``: the backing store failed (details are logged, not returned).

Mutable records (Job, ServiceRequest) carry a ``version``. An update must present the record with
``version == stored version + 1``; otherwise nothing is written. Service events are immutable and
are written only by ``JobRepository.complete``.
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.errors import DomainValidationError, InvalidStateTransitionError
from app.domain.asset import Asset
from app.domain.audit import AuditEvent
from app.domain.business import Business
from app.domain.customer import Customer
from app.domain.enums import AuditEntityType, JobStatus, ServiceRequestStatus
from app.domain.job import Job
from app.domain.service_event import ServiceEvent
from app.domain.service_request import ServiceRequest
from app.domain.technician import Technician

DEFAULT_LIMIT = 100


class BusinessRepository(Protocol):
    def create(self, business: Business) -> None: ...

    def get(self, business_id: str) -> Business: ...


class CustomerRepository(Protocol):
    def create(self, customer: Customer) -> None: ...

    def get(self, business_id: str, customer_id: str) -> Customer: ...

    def list(self, business_id: str, *, limit: int = DEFAULT_LIMIT) -> list[Customer]:
        """Ordered by name."""
        ...

    def find_by_phone(self, business_id: str, phone: str) -> list[Customer]:
        """Customers sharing a phone number. The number is normalized first; an untrustworthy
        number matches nothing. Several matches are possible (shared family phones)."""
        ...

    def search_by_name(
        self, business_id: str, query: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Customer]:
        """Case-insensitive substring match, ordered by name."""
        ...


class AssetRepository(Protocol):
    def create(self, asset: Asset) -> None: ...

    def get(self, business_id: str, asset_id: str) -> Asset: ...

    def list_by_customer(self, business_id: str, customer_id: str) -> list[Asset]:
        """Oldest first."""
        ...

    def find_by_serial(self, business_id: str, serial_number: str) -> list[Asset]: ...


class TechnicianRepository(Protocol):
    def create(self, technician: Technician) -> None: ...

    def get(self, business_id: str, technician_id: str) -> Technician: ...

    def list(self, business_id: str, *, active_only: bool = False) -> list[Technician]:
        """Ordered by name."""
        ...


class ServiceRequestRepository(Protocol):
    def create(self, request: ServiceRequest) -> None:
        """Also reserves ``request.idempotency_key`` (if any) within the business, atomically.
        Raises ``DuplicateRequestError`` when the key is already taken."""
        ...

    def get(self, business_id: str, service_request_id: str) -> ServiceRequest: ...

    def get_by_idempotency_key(self, business_id: str, key: str) -> ServiceRequest | None: ...

    def update(self, request: ServiceRequest) -> None:
        """Versioned. Cannot set JOB_CREATED (use ``JobRepository.create_for_request``) and cannot
        modify a request that is already JOB_CREATED or DISMISSED."""
        ...

    def list(
        self,
        business_id: str,
        *,
        status: ServiceRequestStatus | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[ServiceRequest]:
        """Newest first."""
        ...


class JobRepository(Protocol):
    def create(self, job: Job, audit: AuditEvent) -> None:
        """Job and audit record are written atomically. The job must be NEW."""
        ...

    def create_for_request(self, job: Job, request: ServiceRequest, audit: AuditEvent) -> None:
        """Atomically create the job, link it to ``request`` (which must be the next version, in
        status JOB_CREATED, with ``job_id`` set) and write the audit record. A retry for a request
        that already has a job raises ``ConflictError`` and creates nothing, so a request can never
        yield two jobs."""
        ...

    def get(self, business_id: str, job_id: str) -> Job: ...

    def update(self, job: Job, audit: AuditEvent) -> None:
        """Versioned write of a non-terminal job plus its audit record, atomically. Refuses a
        COMPLETED job: completion goes through ``complete``. Refuses to modify a job that is
        already COMPLETED or CANCELLED."""
        ...

    def complete(self, job: Job, event: ServiceEvent, audit: AuditEvent) -> None:
        """Atomically store the completed job, its service event and the audit record. The stored
        job must be IN_PROGRESS at ``job.version - 1``. All three writes happen or none do."""
        ...

    def list(
        self,
        business_id: str,
        *,
        status: JobStatus | None = None,
        technician_id: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[Job]:
        """Newest first."""
        ...

    def list_by_customer(
        self, business_id: str, customer_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Job]:
        """Newest first."""
        ...

    def list_by_asset(
        self, business_id: str, asset_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[Job]:
        """Newest first."""
        ...


class ServiceEventRepository(Protocol):
    """Read side of service memory. Events are written only by ``JobRepository.complete``."""

    def get(self, business_id: str, event_id: str) -> ServiceEvent: ...

    def list_by_asset(
        self, business_id: str, asset_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[ServiceEvent]:
        """Newest first."""
        ...

    def list_by_customer(
        self, business_id: str, customer_id: str, *, limit: int = DEFAULT_LIMIT
    ) -> list[ServiceEvent]:
        """Newest first."""
        ...


class AuditRepository(Protocol):
    def append(self, audit: AuditEvent) -> None:
        """For mutations not covered by an atomic job write (customer, asset, technician,
        service request creation)."""
        ...

    def list_for_entity(
        self, business_id: str, entity_type: AuditEntityType, entity_id: str
    ) -> list[AuditEvent]:
        """Oldest first."""
        ...


@dataclass(frozen=True, slots=True)
class Repositories:
    businesses: BusinessRepository
    customers: CustomerRepository
    assets: AssetRepository
    technicians: TechnicianRepository
    service_requests: ServiceRequestRepository
    jobs: JobRepository
    service_events: ServiceEventRepository
    audits: AuditRepository


# --- Preconditions shared by every adapter so they enforce identical rules -----------------


def ensure_creatable_job(job: Job) -> None:
    if job.status is not JobStatus.NEW:
        raise DomainValidationError("A job can only be created in the NEW status")


def ensure_updatable_job(job: Job) -> None:
    if job.status is JobStatus.COMPLETED:
        raise InvalidStateTransitionError("A job can only be COMPLETED through job completion")


def ensure_updatable_request(request: ServiceRequest) -> None:
    if request.status is ServiceRequestStatus.JOB_CREATED:
        raise InvalidStateTransitionError(
            "A service request is linked to a job only when the job is created"
        )


def ensure_request_link(job: Job, request: ServiceRequest) -> None:
    consistent = (
        job.business_id == request.business_id
        and job.service_request_id == request.service_request_id
        and request.job_id == job.job_id
        and request.status is ServiceRequestStatus.JOB_CREATED
    )
    if not consistent:
        raise DomainValidationError("The job and service request are not consistently linked")


def ensure_completion_consistent(job: Job, event: ServiceEvent, audit: AuditEvent) -> None:
    consistent = (
        job.status is JobStatus.COMPLETED
        and event.job_id == job.job_id
        and event.asset_id == job.asset_id
        and event.customer_id == job.customer_id
        and event.technician_id == job.technician_id
        and len({job.business_id, event.business_id, audit.business_id}) == 1
    )
    if not consistent:
        raise DomainValidationError("The completed job, service event and audit are inconsistent")
