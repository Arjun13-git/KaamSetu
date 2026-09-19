"""The preserved intake record: reading it back and turning a reviewed request into a job."""

from datetime import datetime

from app.core.context import RequestContext
from app.core.errors import DomainValidationError
from app.core.ids import AssetId, CustomerId
from app.domain.base import DomainModel, LongText
from app.domain.enums import JobSource, ServiceRequestStatus, ServiceType, Urgency
from app.domain.job import TimeSlot
from app.domain.repositories import Repositories
from app.domain.service_request import ServiceRequest
from app.services.job_service import JobCreation, create_job_for_request

_MAX_DESCRIPTION = 2000


class ConfirmJob(DomainModel):
    """A person's decision to turn a request into a job.

    The customer and asset are chosen explicitly; nothing is attached on a guess. Other fields fall
    back to what was extracted (or, for a request with no extraction, the customer's own words).
    """

    customer_id: CustomerId
    asset_id: AssetId
    service_type: ServiceType | None = None
    description: LongText | None = None
    urgency: Urgency | None = None
    preferred_slot: TimeSlot | None = None


def get_request(
    ctx: RequestContext, repos: Repositories, service_request_id: str
) -> ServiceRequest:
    return repos.service_requests.get(ctx.business_id, service_request_id)


def list_requests(
    ctx: RequestContext,
    repos: Repositories,
    *,
    status: ServiceRequestStatus | None,
    limit: int,
) -> list[ServiceRequest]:
    return repos.service_requests.list(ctx.business_id, status=status, limit=limit)


def confirm_job(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    service_request_id: str,
    decision: ConfirmJob,
) -> JobCreation:
    """Create the job for a request. Repeating the call returns the job that already exists."""
    request = repos.service_requests.get(ctx.business_id, service_request_id)
    proposed = proposed_job_fields(request)

    description = decision.description or proposed.description
    if description is None:
        raise DomainValidationError(
            "This request is too long to use as a description; provide a description"
        )
    return create_job_for_request(
        ctx,
        repos,
        now,
        request,
        customer_id=decision.customer_id,
        asset_id=decision.asset_id,
        service_type=decision.service_type or proposed.service_type,
        description=description,
        urgency=decision.urgency or proposed.urgency,
        preferred_slot=decision.preferred_slot or proposed.preferred_slot,
        source=proposed.source,
    )


class ProposedJob(DomainModel):
    service_type: ServiceType
    description: str | None
    urgency: Urgency
    preferred_slot: TimeSlot | None
    source: JobSource


def proposed_job_fields(request: ServiceRequest) -> ProposedJob:
    """What a job for this request would contain if the person supplies nothing else."""
    raw = request.raw_text
    return ProposedJob(
        service_type=ServiceType.UNKNOWN,
        description=raw if len(raw) <= _MAX_DESCRIPTION else None,
        urgency=Urgency.NORMAL,
        preferred_slot=None,
        source=JobSource.MANUAL,
    )
