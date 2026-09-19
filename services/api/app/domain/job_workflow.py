"""Pure job use cases. Each function validates, then returns the new record(s) plus the audit
event that must be persisted with them; nothing here touches storage.

Only ``complete_job`` can produce a COMPLETED job, and it always produces the ServiceEvent
alongside it, so a job can never complete without leaving service memory behind.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from app.core.context import RequestContext
from app.core.errors import (
    ConflictError,
    DomainValidationError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.core.ids import AttachmentId, IdPrefix, ServiceRequestId, new_id
from app.domain.asset import Asset
from app.domain.audit import AuditEvent, build_audit
from app.domain.base import DomainModel, LongText, ShortText
from app.domain.customer import Customer
from app.domain.enums import (
    AuditAction,
    AuditEntityType,
    JobSource,
    JobStatus,
    ServiceType,
    Urgency,
)
from app.domain.job import Job, TimeSlot
from app.domain.job_state_machine import TERMINAL_STATUSES, assert_legal_transition
from app.domain.service_event import ServiceEvent
from app.domain.technician import Technician

_REASSIGNABLE = frozenset(
    {JobStatus.NEW, JobStatus.ASSIGNED, JobStatus.SCHEDULED, JobStatus.ON_THE_WAY}
)
_MAX_TEXT = 2000


@dataclass(frozen=True, slots=True)
class JobChange:
    job: Job
    audit: AuditEvent


@dataclass(frozen=True, slots=True)
class CompletionResult:
    job: Job
    event: ServiceEvent
    audit: AuditEvent


class JobCompletion(DomainModel):
    """What a technician reports when finishing work."""

    work_performed: LongText
    technician_notes: LongText | None = None
    parts_used: list[ShortText] = Field(default_factory=list, max_length=50)
    observed_symptoms: list[ShortText] = Field(default_factory=list, max_length=50)
    follow_up_required: bool = False
    attachment_ids: list[AttachmentId] = Field(default_factory=list, max_length=10)


class JobAmendment(DomainModel):
    """The only fields a PATCH may change. Status, technician and schedule are deliberately
    absent (and unknown fields are rejected), so a PATCH cannot move a job between states."""

    description: LongText | None = None
    urgency: Urgency | None = None
    preferred_slot: TimeSlot | None = None

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> Self:
        for name in ("description", "urgency"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        return self


def create_job(
    ctx: RequestContext,
    *,
    customer: Customer,
    asset: Asset,
    service_type: ServiceType,
    description: str,
    now: datetime,
    urgency: Urgency = Urgency.NORMAL,
    preferred_slot: TimeSlot | None = None,
    source: JobSource = JobSource.MANUAL,
    service_request_id: ServiceRequestId | None = None,
) -> JobChange:
    if customer.business_id != ctx.business_id:
        raise NotFoundError("Customer not found")
    if asset.business_id != ctx.business_id:
        raise NotFoundError("Asset not found")
    if asset.customer_id != customer.customer_id:
        raise DomainValidationError("The asset does not belong to this customer")

    job = Job(
        job_id=new_id(IdPrefix.JOB),
        business_id=ctx.business_id,
        customer_id=customer.customer_id,
        asset_id=asset.asset_id,
        service_type=service_type,
        description=description,
        urgency=urgency,
        preferred_slot=preferred_slot,
        status=JobStatus.NEW,
        source=source,
        service_request_id=service_request_id,
        created_at=now,
        updated_at=now,
    )
    audit = _audit(
        ctx,
        now,
        AuditAction.JOB_CREATED,
        job.job_id,
        {"customer_id": job.customer_id, "asset_id": job.asset_id, "source": source.value},
    )
    return JobChange(job, audit)


def assign_job(ctx: RequestContext, job: Job, technician: Technician, now: datetime) -> JobChange:
    """Assign or reassign. A NEW job becomes ASSIGNED; reassignment never changes status."""
    _require_owned(ctx, job)
    if technician.business_id != ctx.business_id:
        raise NotFoundError("Technician not found")
    if job.status not in _REASSIGNABLE:
        raise InvalidStateTransitionError(f"A {job.status.value} job cannot be assigned")
    if not technician.active:
        raise DomainValidationError("The technician is not active")
    if job.technician_id == technician.technician_id:
        raise DomainValidationError("The job is already assigned to this technician")

    status = JobStatus.ASSIGNED if job.status is JobStatus.NEW else job.status
    assigned = _advance(job, now, status=status, technician_id=technician.technician_id)
    audit = _audit(
        ctx,
        now,
        AuditAction.JOB_ASSIGNED,
        job.job_id,
        {
            "technician_id": technician.technician_id,
            "previous_technician_id": job.technician_id,
            "status": status.value,
        },
    )
    return JobChange(assigned, audit)


def transition_job(
    ctx: RequestContext,
    job: Job,
    to_status: JobStatus,
    now: datetime,
    *,
    scheduled_slot: TimeSlot | None = None,
) -> JobChange:
    """Move a job along its normal progression, or cancel it.

    ASSIGNED and COMPLETED cannot be requested here: the first needs a technician, the second
    must create the service event and goes through ``complete_job``.
    """
    _require_owned(ctx, job)
    if to_status is JobStatus.COMPLETED:
        raise InvalidStateTransitionError("A job can only be COMPLETED through job completion")
    if to_status is JobStatus.ASSIGNED:
        raise InvalidStateTransitionError("A job becomes ASSIGNED by assigning a technician")
    assert_legal_transition(job.status, to_status)

    changes: dict[str, object] = {"status": to_status}
    if to_status is JobStatus.SCHEDULED:
        slot = scheduled_slot or job.scheduled_slot
        if slot is None:
            raise DomainValidationError("Scheduling requires a scheduled slot")
        changes["scheduled_slot"] = slot
    elif scheduled_slot is not None:
        raise DomainValidationError("A scheduled slot can only be set when scheduling")

    moved = _advance(job, now, **changes)
    audit = _audit(
        ctx,
        now,
        AuditAction.JOB_STATUS_CHANGED,
        job.job_id,
        {"from": job.status.value, "to": to_status.value},
    )
    return JobChange(moved, audit)


def amend_job(ctx: RequestContext, job: Job, amendment: JobAmendment, now: datetime) -> JobChange:
    _require_owned(ctx, job)
    if job.status in TERMINAL_STATUSES:
        raise ConflictError(f"A {job.status.value} job can no longer be changed")
    changes = {name: getattr(amendment, name) for name in amendment.model_fields_set}
    if not changes:
        raise DomainValidationError("No changes were supplied")

    amended = _advance(job, now, **changes)
    audit = _audit(
        ctx,
        now,
        AuditAction.JOB_AMENDED,
        job.job_id,
        {"fields": ",".join(sorted(changes))},
    )
    return JobChange(amended, audit)


def complete_job(
    ctx: RequestContext, job: Job, completion: JobCompletion, now: datetime
) -> CompletionResult:
    """The only route to COMPLETED. Returns the completed job, the service event and the audit
    record; the caller must persist all three atomically."""
    _require_owned(ctx, job)
    if job.status is not JobStatus.IN_PROGRESS or job.technician_id is None:
        raise InvalidStateTransitionError(
            f"Only an IN_PROGRESS job can be completed (this job is {job.status.value})"
        )

    event = ServiceEvent(
        event_id=new_id(IdPrefix.SERVICE_EVENT),
        business_id=job.business_id,
        asset_id=job.asset_id,
        customer_id=job.customer_id,
        job_id=job.job_id,
        technician_id=job.technician_id,
        summary=_summarize(job, completion),
        work_performed=completion.work_performed,
        technician_notes=completion.technician_notes,
        parts_used=completion.parts_used,
        observed_symptoms=completion.observed_symptoms,
        follow_up_required=completion.follow_up_required,
        attachments=completion.attachment_ids,
        timestamp=now,
    )
    completed = _advance(job, now, status=JobStatus.COMPLETED, completed_at=now)
    audit = _audit(
        ctx,
        now,
        AuditAction.JOB_COMPLETED,
        job.job_id,
        {"service_event_id": event.event_id},
    )
    return CompletionResult(completed, event, audit)


def _advance(job: Job, now: datetime, **changes: object) -> Job:
    return job.evolve(updated_at=now, version=job.version + 1, **changes)


def _require_owned(ctx: RequestContext, job: Job) -> None:
    if job.business_id != ctx.business_id:
        raise NotFoundError("Job not found")


def _audit(
    ctx: RequestContext,
    now: datetime,
    action: AuditAction,
    job_id: str,
    metadata: dict[str, str | int | bool | None],
) -> AuditEvent:
    return build_audit(ctx, now, action, AuditEntityType.JOB, job_id, metadata)


def _summarize(job: Job, completion: JobCompletion) -> str:
    """A deterministic restatement of what was recorded. It adds no diagnosis or inference."""
    text = f"Reported: {job.description} | Work performed: {completion.work_performed}"
    return text if len(text) <= _MAX_TEXT else text[: _MAX_TEXT - 1] + "…"
