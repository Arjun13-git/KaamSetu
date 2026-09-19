"""Builders for valid domain objects. Override any field with keyword arguments."""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.context import Actor, RequestContext
from app.core.ids import IdPrefix, new_id
from app.domain.asset import Asset
from app.domain.business import Business
from app.domain.customer import Customer
from app.domain.enums import AssetType, JobSource, JobStatus, ServiceType
from app.domain.job import Job
from app.domain.service_event import ServiceEvent
from app.domain.service_request import ServiceRequest
from app.domain.technician import Technician

NOW = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
BUSINESS_ID = "bus_test"
OTHER_BUSINESS_ID = "bus_other"


def make_ctx(business_id: str = BUSINESS_ID) -> RequestContext:
    return RequestContext(Actor(business_id=business_id, actor_id="usr_test"), "req_test0001")


def make_business(**overrides: Any) -> Business:
    fields: dict[str, Any] = {
        "business_id": BUSINESS_ID,
        "name": "Test Cooling Care",
        "timezone": "Asia/Kolkata",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Business(**{**fields, **overrides})


def make_customer(**overrides: Any) -> Customer:
    fields: dict[str, Any] = {
        "customer_id": new_id(IdPrefix.CUSTOMER),
        "business_id": BUSINESS_ID,
        "name": "Ravi Kumar",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Customer(**{**fields, **overrides})


def make_asset(customer: Customer | None = None, **overrides: Any) -> Asset:
    owner = customer or make_customer()
    fields: dict[str, Any] = {
        "asset_id": new_id(IdPrefix.ASSET),
        "business_id": owner.business_id,
        "customer_id": owner.customer_id,
        "asset_type": AssetType.AIR_CONDITIONER,
        "brand": "LG",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Asset(**{**fields, **overrides})


def make_technician(**overrides: Any) -> Technician:
    fields: dict[str, Any] = {
        "technician_id": new_id(IdPrefix.TECHNICIAN),
        "business_id": BUSINESS_ID,
        "name": "Imran Sheikh",
        "skills": ["air_conditioner"],
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Technician(**{**fields, **overrides})


def make_service_request(**overrides: Any) -> ServiceRequest:
    fields: dict[str, Any] = {
        "service_request_id": new_id(IdPrefix.SERVICE_REQUEST),
        "business_id": BUSINESS_ID,
        "raw_text": "Bhaiya LG AC thanda nahi kar raha",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return ServiceRequest(**{**fields, **overrides})


def make_job(customer: Customer | None = None, asset: Asset | None = None, **overrides: Any) -> Job:
    owner = customer or make_customer()
    item = asset or make_asset(owner)
    fields: dict[str, Any] = {
        "job_id": new_id(IdPrefix.JOB),
        "business_id": owner.business_id,
        "customer_id": owner.customer_id,
        "asset_id": item.asset_id,
        "service_type": ServiceType.REPAIR,
        "description": "AC not cooling",
        "source": JobSource.MANUAL,
        "status": JobStatus.NEW,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Job(**{**fields, **overrides})


def make_service_event(job: Job, **overrides: Any) -> ServiceEvent:
    fields: dict[str, Any] = {
        "event_id": new_id(IdPrefix.SERVICE_EVENT),
        "business_id": job.business_id,
        "asset_id": job.asset_id,
        "customer_id": job.customer_id,
        "job_id": job.job_id,
        "technician_id": job.technician_id or new_id(IdPrefix.TECHNICIAN),
        "summary": "AC not cooling; filter cleaned",
        "work_performed": "Cleaned filter",
        "timestamp": LATER,
    }
    return ServiceEvent(**{**fields, **overrides})
