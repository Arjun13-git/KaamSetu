"""Job use cases over the repositories. The state rules live in ``domain.job_workflow``; this layer
loads records inside the caller's business, applies a workflow function and persists the result
with its audit record (atomically, via the repository).

Every job originates from a ServiceRequest, the preserved intake record. Creation is therefore
idempotent: the request is linked to its job in one atomic write, so a retry can only ever find
the job that already exists.
"""

from dataclasses import dataclass
from datetime import datetime

from app.core.context import RequestContext
from app.core.errors import (
    ConflictError,
    DomainValidationError,
    DuplicateRequestError,
)
from app.core.ids import AssetId, CustomerId, IdPrefix, TechnicianId, new_id
from app.domain import job_workflow
from app.domain.audit import build_audit
from app.domain.base import DomainModel, LongText
from app.domain.enums import (
    AuditAction,
    AuditEntityType,
    JobSource,
    JobStatus,
    ResolutionState,
    ServiceRequestStatus,
    ServiceType,
    Urgency,
)
from app.domain.job import Job, TimeSlot
from app.domain.job_workflow import CompletionResult, JobAmendment, JobCompletion
from app.domain.repositories import Repositories
from app.domain.service_request import EntityResolution, ServiceRequest


class NewJob(DomainModel):
    customer_id: CustomerId
    asset_id: AssetId
    service_type: ServiceType
    description: LongText
    urgency: Urgency = Urgency.NORMAL
    preferred_slot: TimeSlot | None = None


class JobAssignment(DomainModel):
    technician_id: TechnicianId


class JobTransition(DomainModel):
    to_status: JobStatus
    scheduled_slot: TimeSlot | None = None


@dataclass(frozen=True, slots=True)
class JobCreation:
    job: Job
    created: bool


def create_manual_job(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    data: NewJob,
    idempotency_key: str | None,
) -> JobCreation:
    """Create a job from operator-entered fields. With an idempotency key, repeating the call
    returns the original job instead of creating another."""
    customer = repos.customers.get(ctx.business_id, data.customer_id)
    asset = repos.assets.get(ctx.business_id, data.asset_id)
    if asset.customer_id != customer.customer_id:
        raise DomainValidationError("The asset does not belong to this customer")

    request = _manual_request(ctx, repos, now, data, idempotency_key)
    return create_job_for_request(
        ctx,
        repos,
        now,
        request,
        customer_id=data.customer_id,
        asset_id=data.asset_id,
        service_type=data.service_type,
        description=data.description,
        urgency=data.urgency,
        preferred_slot=data.preferred_slot,
        source=JobSource.MANUAL,
    )


def create_job_for_request(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    request: ServiceRequest,
    *,
    customer_id: str,
    asset_id: str,
    service_type: ServiceType,
    description: str,
    urgency: Urgency,
    preferred_slot: TimeSlot | None,
    source: JobSource,
) -> JobCreation:
    """Create the job for ``request`` and link them atomically. If the request already has a job
    (a retry, or a concurrent duplicate) that job is returned and nothing new is created."""
    if request.status is ServiceRequestStatus.JOB_CREATED and request.job_id:
        return JobCreation(repos.jobs.get(ctx.business_id, request.job_id), created=False)
    if request.status is ServiceRequestStatus.DISMISSED:
        raise ConflictError("A dismissed service request cannot start a job")

    customer = repos.customers.get(ctx.business_id, customer_id)
    asset = repos.assets.get(ctx.business_id, asset_id)
    change = job_workflow.create_job(
        ctx,
        customer=customer,
        asset=asset,
        service_type=service_type,
        description=description,
        now=now,
        urgency=urgency,
        preferred_slot=preferred_slot,
        source=source,
        service_request_id=request.service_request_id,
    )
    linked = request.evolve(
        status=ServiceRequestStatus.JOB_CREATED,
        job_id=change.job.job_id,
        customer_resolution=EntityResolution(
            state=ResolutionState.EXISTING,
            entity_id=customer_id,
            candidates=request.customer_resolution.candidates,
        ),
        asset_resolution=EntityResolution(
            state=ResolutionState.EXISTING,
            entity_id=asset_id,
            candidates=request.asset_resolution.candidates,
        ),
        version=request.version + 1,
        updated_at=now,
    )
    try:
        repos.jobs.create_for_request(change.job, linked, change.audit)
    except ConflictError:
        current = repos.service_requests.get(ctx.business_id, request.service_request_id)
        if current.job_id is not None:
            return JobCreation(repos.jobs.get(ctx.business_id, current.job_id), created=False)
        raise
    return JobCreation(change.job, created=True)


def _manual_request(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    data: NewJob,
    idempotency_key: str | None,
) -> ServiceRequest:
    if idempotency_key is not None:
        existing = repos.service_requests.get_by_idempotency_key(ctx.business_id, idempotency_key)
        if existing is not None:
            return _same_manual_request(existing, data)

    request = ServiceRequest(
        service_request_id=new_id(IdPrefix.SERVICE_REQUEST),
        business_id=ctx.business_id,
        raw_text=data.description,
        customer_resolution=EntityResolution(
            state=ResolutionState.EXISTING, entity_id=data.customer_id
        ),
        asset_resolution=EntityResolution(state=ResolutionState.EXISTING, entity_id=data.asset_id),
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )
    try:
        repos.service_requests.create(request)
    except DuplicateRequestError:
        # A concurrent call with the same key won the race.
        assert idempotency_key is not None
        existing = repos.service_requests.get_by_idempotency_key(ctx.business_id, idempotency_key)
        if existing is None:
            raise
        return _same_manual_request(existing, data)
    repos.audits.append(
        build_audit(
            ctx,
            now,
            AuditAction.SERVICE_REQUEST_CREATED,
            AuditEntityType.SERVICE_REQUEST,
            request.service_request_id,
        )
    )
    return request


def _same_manual_request(existing: ServiceRequest, data: NewJob) -> ServiceRequest:
    """A key may be reused only to repeat the same request, never to smuggle in a different one."""
    same = (
        existing.raw_text == data.description
        and existing.customer_resolution.entity_id == data.customer_id
        and existing.asset_resolution.entity_id == data.asset_id
    )
    if not same:
        raise DuplicateRequestError("This idempotency key was already used for a different request")
    return existing


def get_job(ctx: RequestContext, repos: Repositories, job_id: str) -> Job:
    return repos.jobs.get(ctx.business_id, job_id)


def list_jobs(
    ctx: RequestContext,
    repos: Repositories,
    *,
    status: JobStatus | None,
    technician_id: str | None,
    limit: int,
) -> list[Job]:
    return repos.jobs.list(ctx.business_id, status=status, technician_id=technician_id, limit=limit)


def amend_job(
    ctx: RequestContext, repos: Repositories, now: datetime, job_id: str, amendment: JobAmendment
) -> Job:
    job = repos.jobs.get(ctx.business_id, job_id)
    change = job_workflow.amend_job(ctx, job, amendment, now)
    repos.jobs.update(change.job, change.audit)
    return change.job


def assign_job(
    ctx: RequestContext, repos: Repositories, now: datetime, job_id: str, technician_id: str
) -> Job:
    job = repos.jobs.get(ctx.business_id, job_id)
    technician = repos.technicians.get(ctx.business_id, technician_id)
    change = job_workflow.assign_job(ctx, job, technician, now)
    repos.jobs.update(change.job, change.audit)
    return change.job


def transition_job(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    job_id: str,
    transition: JobTransition,
) -> Job:
    job = repos.jobs.get(ctx.business_id, job_id)
    change = job_workflow.transition_job(
        ctx, job, transition.to_status, now, scheduled_slot=transition.scheduled_slot
    )
    repos.jobs.update(change.job, change.audit)
    return change.job


def complete_job(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    job_id: str,
    completion: JobCompletion,
) -> CompletionResult:
    """The only way a job becomes COMPLETED: job, service event and audit are stored together."""
    if completion.attachment_ids:
        # Attachments are not stored yet; never record references to objects that do not exist.
        raise DomainValidationError("Attachments are not supported yet")
    job = repos.jobs.get(ctx.business_id, job_id)
    result = job_workflow.complete_job(ctx, job, completion, now)
    repos.jobs.complete(result.job, result.event, result.audit)
    return result
