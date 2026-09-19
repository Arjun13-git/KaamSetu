from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.api.deps import (
    ClockDep,
    ExtractorDep,
    IdempotencyKeyHeader,
    RepositoriesDep,
    RequestContextDep,
    SettingsDep,
)
from app.api.envelope import SuccessEnvelope
from app.api.schemas import JobOut, ServiceEventOut, ServiceRequestOut, success
from app.domain.enums import ServiceRequestStatus
from app.services import intake_service
from app.services.intake_service import IntakeRequest

router = APIRouter(tags=["intake"])


class IntakeOut(BaseModel):
    """What was understood and what happened next, with the uncertainty left visible.

    ``outcome`` says what the operator should do: nothing (a job was created), review the proposed
    fields and resolution, or fill the job in by hand because AI could not help.
    """

    outcome: Literal["job_created", "needs_review", "manual_entry_required"]
    service_request: ServiceRequestOut
    job: JobOut | None
    prior_service: list[ServiceEventOut]
    safety_concern: bool


@router.post("/intake", status_code=201)
def intake(
    body: IntakeRequest,
    response: Response,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
    extractor: ExtractorDep,
    settings: SettingsDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> SuccessEnvelope[IntakeOut]:
    """Turn a customer message (and optional photo) into a preserved ServiceRequest, and into a job
    when the customer and asset are unambiguous. Send an ``Idempotency-Key`` so a retry returns the
    same result (200) without calling the model again."""
    result = intake_service.process_intake(
        ctx,
        repos,
        clock(),
        extractor,
        body,
        idempotency_key=idempotency_key,
        default_timezone=settings.default_timezone,
    )
    if not result.created:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"

    status = result.request.status
    outcome: Literal["job_created", "needs_review", "manual_entry_required"] = (
        "job_created"
        if status is ServiceRequestStatus.JOB_CREATED
        else "manual_entry_required"
        if status is ServiceRequestStatus.EXTRACTION_FAILED
        else "needs_review"
    )
    return success(
        ctx,
        IntakeOut(
            outcome=outcome,
            service_request=ServiceRequestOut.model_validate(result.request),
            job=JobOut.model_validate(result.job) if result.job else None,
            prior_service=[ServiceEventOut.model_validate(e) for e in result.prior_service],
            safety_concern=result.safety_concern,
        ),
    )
