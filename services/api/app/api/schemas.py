"""Public response shapes. They are built from domain records but never expose the owning business
or any storage detail; the tenant is implied by the caller."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.api.envelope import SuccessEnvelope
from app.core.context import RequestContext
from app.domain.enums import (
    AssetType,
    JobSource,
    JobStatus,
    ServiceRequestStatus,
    ServiceType,
    Urgency,
)
from app.domain.job import TimeSlot
from app.domain.service_request import EntityResolution


def success[T](ctx: RequestContext, data: T) -> SuccessEnvelope[T]:
    return SuccessEnvelope(data=data, request_id=ctx.request_id)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerOut(_Out):
    customer_id: str
    name: str
    phone: str | None
    email: str | None
    address: str | None
    preferred_language: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class TechnicianOut(_Out):
    technician_id: str
    name: str
    phone: str | None
    skills: list[str]
    active: bool
    created_at: datetime
    updated_at: datetime


class AssetOut(_Out):
    asset_id: str
    customer_id: str
    asset_type: AssetType
    brand: str | None
    model: str | None
    serial_number: str | None
    purchase_date: date | None
    warranty_until: date | None
    location: str | None
    metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime


class JobOut(_Out):
    job_id: str
    customer_id: str
    asset_id: str
    service_type: ServiceType
    description: str
    urgency: Urgency
    preferred_slot: TimeSlot | None
    scheduled_slot: TimeSlot | None
    technician_id: str | None
    status: JobStatus
    source: JobSource
    service_request_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ServiceEventOut(_Out):
    event_id: str
    asset_id: str
    customer_id: str
    job_id: str
    technician_id: str
    summary: str
    work_performed: str
    technician_notes: str | None
    parts_used: list[str]
    observed_symptoms: list[str]
    follow_up_required: bool
    attachments: list[str]
    timestamp: datetime


class ServiceRequestOut(_Out):
    service_request_id: str
    status: ServiceRequestStatus
    raw_text: str
    extraction: dict[str, Any] | None
    customer_resolution: EntityResolution
    asset_resolution: EntityResolution
    failure_reason: str | None
    job_id: str | None
    created_at: datetime
    updated_at: datetime


class JobCompletionOut(BaseModel):
    job: JobOut
    service_event: ServiceEventOut


class JobCardOut(BaseModel):
    """What a technician needs before arriving: the job, who and what, and prior service of the
    same asset exactly as it was recorded."""

    job: JobOut
    customer: CustomerOut
    asset: AssetOut
    technician: TechnicianOut | None
    prior_service: list[ServiceEventOut]


class AssetHistoryOut(BaseModel):
    asset: AssetOut
    jobs: list[JobOut]
    service_events: list[ServiceEventOut]


class CustomerHistoryOut(BaseModel):
    customer: CustomerOut
    assets: list[AssetOut]
    jobs: list[JobOut]
    service_events: list[ServiceEventOut]
