from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import ClockDep, IdempotencyKeyHeader, RepositoriesDep, RequestContextDep
from app.api.envelope import SuccessEnvelope
from app.api.schemas import (
    AssetOut,
    CustomerOut,
    JobCardOut,
    JobCompletionOut,
    JobOut,
    ServiceEventOut,
    TechnicianOut,
    success,
)
from app.core.ids import JobId, TechnicianId
from app.domain.enums import JobStatus
from app.domain.job_workflow import JobAmendment, JobCompletion
from app.services import history_service, job_service
from app.services.job_service import JobAssignment, JobTransition, NewJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=201)
def create_job(
    body: NewJob,
    response: Response,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> SuccessEnvelope[JobOut]:
    """Create a job from operator-entered fields. Send an ``Idempotency-Key`` so a retry returns the
    original job (200) instead of creating another."""
    creation = job_service.create_manual_job(ctx, repos, clock(), body, idempotency_key)
    if not creation.created:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
    return success(ctx, JobOut.model_validate(creation.job))


@router.get("")
def list_jobs(
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    status: JobStatus | None = None,
    technician_id: TechnicianId | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SuccessEnvelope[list[JobOut]]:
    jobs = job_service.list_jobs(
        ctx, repos, status=status, technician_id=technician_id, limit=limit
    )
    return success(ctx, [JobOut.model_validate(j) for j in jobs])


@router.get("/{job_id}")
def get_job(
    job_id: JobId, ctx: RequestContextDep, repos: RepositoriesDep
) -> SuccessEnvelope[JobCardOut]:
    """The technician-facing job card: the job, customer, asset and prior service of that asset."""
    card = history_service.job_card(ctx, repos, job_id)
    return success(
        ctx,
        JobCardOut(
            job=JobOut.model_validate(card.job),
            customer=CustomerOut.model_validate(card.customer),
            asset=AssetOut.model_validate(card.asset),
            technician=TechnicianOut.model_validate(card.technician) if card.technician else None,
            prior_service=[ServiceEventOut.model_validate(e) for e in card.prior_events],
        ),
    )


@router.patch("/{job_id}")
def amend_job(
    job_id: JobId,
    body: JobAmendment,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
) -> SuccessEnvelope[JobOut]:
    """Change description, urgency or preferred slot. Status is not editable here."""
    job = job_service.amend_job(ctx, repos, clock(), job_id, body)
    return success(ctx, JobOut.model_validate(job))


@router.post("/{job_id}/assign")
def assign_job(
    job_id: JobId,
    body: JobAssignment,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
) -> SuccessEnvelope[JobOut]:
    job = job_service.assign_job(ctx, repos, clock(), job_id, body.technician_id)
    return success(ctx, JobOut.model_validate(job))


@router.post("/{job_id}/transition")
def transition_job(
    job_id: JobId,
    body: JobTransition,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
) -> SuccessEnvelope[JobOut]:
    """Move a job along its progression or cancel it. COMPLETED is not reachable here."""
    job = job_service.transition_job(ctx, repos, clock(), job_id, body)
    return success(ctx, JobOut.model_validate(job))


@router.post("/{job_id}/complete")
def complete_job(
    job_id: JobId,
    body: JobCompletion,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
) -> SuccessEnvelope[JobCompletionOut]:
    """Complete an IN_PROGRESS job: stores the completed job, its service event and an audit
    record atomically."""
    result = job_service.complete_job(ctx, repos, clock(), job_id, body)
    return success(
        ctx,
        JobCompletionOut(
            job=JobOut.model_validate(result.job),
            service_event=ServiceEventOut.model_validate(result.event),
        ),
    )
