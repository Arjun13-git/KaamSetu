"""Conversation to work: customer text (and an optional photo) becomes a preserved ServiceRequest,
is understood by the model, resolved deterministically, and becomes a Job only when the evidence
is clear.

The model proposes structured data and nothing else. Everything below is ordinary application code:
the request is stored *before* the model is called (so it is never lost), the model's answer is
validated and guarded, identity is resolved from explicit evidence, and the job is created through
the same atomic, idempotent path as every other job. If the model is unavailable or answers badly,
the request stays as it is for a person to complete.
"""

import base64
import binascii
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator

from app.ai.extractor import IntakeExtractor
from app.ai.guards import detect_safety_concern
from app.ai.provider import ImageFormat, ImageInput
from app.ai.schemas import Intent, StoredExtraction
from app.core.context import RequestContext
from app.core.errors import AiInvalidOutputError, AiUnavailableError, DuplicateRequestError
from app.core.ids import CustomerId, IdPrefix, new_id
from app.domain.audit import build_audit
from app.domain.base import DomainModel
from app.domain.enums import (
    AuditAction,
    AuditEntityType,
    JobSource,
    ResolutionState,
    ServiceRequestStatus,
    ServiceType,
    Urgency,
)
from app.domain.job import Job
from app.domain.normalization import normalize_phone
from app.domain.repositories import Repositories
from app.domain.service_event import ServiceEvent
from app.domain.service_request import EntityResolution, RawText, ServiceRequest
from app.services.history_service import prior_service
from app.services.job_service import create_job_for_request
from app.services.resolution import resolve_asset, resolve_customer
from app.services.scheduling import business_timezone, local_today, preferred_slot

# A job is created without a person only when the model was at least this sure overall.
AUTO_CREATE_MIN_CONFIDENCE = 0.7

_MAX_IMAGE_BYTES = 3_750_000  # the model's per-image limit
_MEDIA_TYPES: dict[str, ImageFormat] = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_MAGIC: dict[ImageFormat, Callable[[bytes], bool]] = {
    "jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "gif": lambda b: b[:6] in (b"GIF87a", b"GIF89a"),
    "webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}


class ImageUpload(DomainModel):
    """A photo sent inline. It is checked, shown to the model and then discarded: nothing is stored
    until attachment storage exists."""

    media_type: Literal["image/jpeg", "image/png", "image/webp", "image/gif"]
    data_base64: str = Field(min_length=1, max_length=5_200_000)

    @field_validator("data_base64")
    @classmethod
    def _valid_image(cls, value: str, info: ValidationInfo) -> str:
        media_type = info.data.get("media_type")
        try:
            raw = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("image is not valid base64") from exc
        if len(raw) > _MAX_IMAGE_BYTES:
            raise ValueError("image is too large")
        kind = _MEDIA_TYPES.get(media_type or "")
        if kind is None or not _MAGIC[kind](raw):
            raise ValueError("image content does not match its declared type")
        return value

    def to_input(self) -> ImageInput:
        kind = _MEDIA_TYPES[self.media_type]
        return ImageInput(format=kind, data=base64.b64decode(self.data_base64))


class IntakeRequest(DomainModel):
    """What the operator submits. ``customer_id`` and ``phone`` are optional context from the
    conversation (who is writing); they are looked up inside the caller's business and never grant
    access to anything."""

    text: RawText
    customer_id: CustomerId | None = None
    phone: str | None = None
    image: ImageUpload | None = None

    @field_validator("phone")
    @classmethod
    def _normalize(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_phone(value)
        if normalized is None:
            raise ValueError("phone number is not valid")
        return normalized


@dataclass(frozen=True, slots=True)
class IntakeResult:
    request: ServiceRequest
    job: Job | None
    prior_service: list[ServiceEvent]
    safety_concern: bool
    created: bool


def process_intake(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    extractor: IntakeExtractor,
    data: IntakeRequest,
    *,
    idempotency_key: str | None,
    default_timezone: str,
) -> IntakeResult:
    if data.customer_id is not None:
        repos.customers.get(ctx.business_id, data.customer_id)  # NotFoundError across tenants

    request, created = _obtain_request(ctx, repos, now, data, idempotency_key)
    if request.status is not ServiceRequestStatus.RECEIVED:
        return _result_for(ctx, repos, request, created)  # a replay: never call the model again

    timezone = business_timezone(ctx, repos, default_timezone)
    try:
        stored = extractor.extract(
            text=data.text,
            today=local_today(now, timezone),
            timezone=timezone,
            image=data.image.to_input() if data.image else None,
        )
    except (AiUnavailableError, AiInvalidOutputError) as failure:
        failed = request.evolve(
            status=ServiceRequestStatus.EXTRACTION_FAILED,
            failure_reason=failure.code.value,
            customer_resolution=resolve_customer(
                repos,
                ctx.business_id,
                customer_id=data.customer_id,
                phone=data.phone,
                name_hint=None,
            ),
            version=request.version + 1,
            updated_at=now,
        )
        repos.service_requests.update(failed)
        # Safety wording is detected without the model, so it is flagged even when AI is down.
        return IntakeResult(failed, None, [], detect_safety_concern(data.text), created)

    extraction = stored.data
    customer = resolve_customer(
        repos,
        ctx.business_id,
        customer_id=data.customer_id,
        phone=data.phone,
        name_hint=extraction.customer_reference,
    )
    asset = resolve_asset(
        repos, ctx.business_id, customer, extraction.asset, extraction.confidence.asset
    )
    reviewed = request.evolve(
        status=ServiceRequestStatus.NEEDS_REVIEW,
        extraction=stored.model_dump(mode="json"),
        customer_resolution=customer,
        asset_resolution=asset,
        version=request.version + 1,
        updated_at=now,
    )
    repos.service_requests.update(reviewed)

    job = None
    if _clear_enough_to_create_a_job(stored, customer, asset):
        assert customer.entity_id and asset.entity_id and extraction.problem.description
        creation = create_job_for_request(
            ctx,
            repos,
            now,
            reviewed,
            customer_id=customer.entity_id,
            asset_id=asset.entity_id,
            service_type=extraction.service_type,
            description=extraction.problem.description,
            urgency=extraction.problem.urgency or Urgency.NORMAL,
            preferred_slot=preferred_slot(extraction.time_preference, timezone),
            source=JobSource.INTAKE,
        )
        job = creation.job

    final = repos.service_requests.get(ctx.business_id, request.service_request_id)
    history = (
        prior_service(ctx, repos, asset.entity_id, exclude_job_id=job.job_id if job else None)
        if asset.state is ResolutionState.EXISTING and asset.entity_id
        else []
    )
    return IntakeResult(final, job, history, stored.safety_concern, created)


def _clear_enough_to_create_a_job(
    stored: StoredExtraction, customer: EntityResolution, asset: EntityResolution
) -> bool:
    """Everything a person would otherwise confirm is already settled by explicit evidence."""
    data = stored.data
    return (
        data.intent is Intent.SERVICE_REQUEST
        and data.service_type is not ServiceType.UNKNOWN
        and bool(data.problem.description)
        and data.confidence.overall >= AUTO_CREATE_MIN_CONFIDENCE
        and customer.state is ResolutionState.EXISTING
        and asset.state is ResolutionState.EXISTING
    )


def _obtain_request(
    ctx: RequestContext,
    repos: Repositories,
    now: datetime,
    data: IntakeRequest,
    idempotency_key: str | None,
) -> tuple[ServiceRequest, bool]:
    """Find the request for this idempotency key, or store a new one before any model call."""
    if idempotency_key is not None:
        existing = repos.service_requests.get_by_idempotency_key(ctx.business_id, idempotency_key)
        if existing is not None:
            return _same_intake(existing, data), False

    request = ServiceRequest(
        service_request_id=new_id(IdPrefix.SERVICE_REQUEST),
        business_id=ctx.business_id,
        raw_text=data.text,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )
    try:
        repos.service_requests.create(request)
    except DuplicateRequestError:
        assert idempotency_key is not None
        existing = repos.service_requests.get_by_idempotency_key(ctx.business_id, idempotency_key)
        if existing is None:
            raise
        return _same_intake(existing, data), False
    repos.audits.append(
        build_audit(
            ctx,
            now,
            AuditAction.SERVICE_REQUEST_CREATED,
            AuditEntityType.SERVICE_REQUEST,
            request.service_request_id,
        )
    )
    return request, True


def _same_intake(existing: ServiceRequest, data: IntakeRequest) -> ServiceRequest:
    """A key can only repeat the same message, never carry a different one."""
    if existing.raw_text != data.text:
        raise DuplicateRequestError("This idempotency key was already used for a different request")
    return existing


def _result_for(
    ctx: RequestContext, repos: Repositories, request: ServiceRequest, created: bool
) -> IntakeResult:
    job = repos.jobs.get(ctx.business_id, request.job_id) if request.job_id else None
    asset = request.asset_resolution
    history = (
        prior_service(ctx, repos, asset.entity_id, exclude_job_id=request.job_id)
        if asset.state is ResolutionState.EXISTING and asset.entity_id
        else []
    )
    stored_flag = (
        StoredExtraction.model_validate(request.extraction).safety_concern
        if request.extraction
        else False
    )
    safety = stored_flag or detect_safety_concern(request.raw_text)
    return IntakeResult(request, job, history, safety, created)
