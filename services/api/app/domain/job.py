from typing import Self

from pydantic import model_validator

from app.core.ids import AssetId, BusinessId, CustomerId, JobId, ServiceRequestId, TechnicianId
from app.domain.base import DomainModel, LongText, TimestampedModel, UtcDatetime
from app.domain.enums import JobSource, JobStatus, ServiceType, Urgency

_STATUSES_REQUIRING_TECHNICIAN = frozenset(
    {
        JobStatus.ASSIGNED,
        JobStatus.SCHEDULED,
        JobStatus.ON_THE_WAY,
        JobStatus.IN_PROGRESS,
        JobStatus.COMPLETED,
    }
)


class TimeSlot(DomainModel):
    start: UtcDatetime
    end: UtcDatetime | None = None

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        if self.end is not None and self.end <= self.start:
            raise ValueError("slot end must be after slot start")
        return self


class Job(TimestampedModel):
    """The operational work record. Status changes go through ``job_workflow``, never by
    editing fields directly; ``version`` supports optimistic concurrency in persistence."""

    job_id: JobId
    business_id: BusinessId
    customer_id: CustomerId
    asset_id: AssetId
    service_type: ServiceType
    description: LongText
    urgency: Urgency = Urgency.NORMAL
    preferred_slot: TimeSlot | None = None
    scheduled_slot: TimeSlot | None = None
    technician_id: TechnicianId | None = None
    status: JobStatus = JobStatus.NEW
    source: JobSource
    service_request_id: ServiceRequestId | None = None
    version: int = 1
    completed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.version < 1:
            raise ValueError("version must be at least 1")
        if self.status is JobStatus.NEW and self.technician_id is not None:
            raise ValueError("a NEW job cannot have a technician")
        if self.status in _STATUSES_REQUIRING_TECHNICIAN and self.technician_id is None:
            raise ValueError(f"a {self.status.value} job requires a technician")
        if self.status is JobStatus.SCHEDULED and self.scheduled_slot is None:
            raise ValueError("a SCHEDULED job requires a scheduled slot")
        if (self.status is JobStatus.COMPLETED) != (self.completed_at is not None):
            raise ValueError("completed_at must be set if and only if the job is COMPLETED")
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("completed_at cannot be earlier than created_at")
        if self.source is JobSource.INTAKE and self.service_request_id is None:
            raise ValueError("an intake job must reference its service request")
        return self
