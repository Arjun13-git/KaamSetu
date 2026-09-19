from pydantic import Field

from app.core.ids import (
    AssetId,
    AttachmentId,
    BusinessId,
    CustomerId,
    JobId,
    ServiceEventId,
    TechnicianId,
)
from app.domain.base import DomainModel, LongText, ShortText, UtcDatetime


class ServiceEvent(DomainModel):
    """An immutable historical record of completed work. It is the unit of service memory:
    it states what was recorded, never a diagnosis."""

    event_id: ServiceEventId
    business_id: BusinessId
    asset_id: AssetId
    customer_id: CustomerId
    job_id: JobId
    technician_id: TechnicianId
    summary: LongText
    work_performed: LongText
    technician_notes: LongText | None = None
    parts_used: list[ShortText] = Field(default_factory=list, max_length=50)
    observed_symptoms: list[ShortText] = Field(default_factory=list, max_length=50)
    follow_up_required: bool = False
    attachments: list[AttachmentId] = Field(default_factory=list, max_length=10)
    timestamp: UtcDatetime
