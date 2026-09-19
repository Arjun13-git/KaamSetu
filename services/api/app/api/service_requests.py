from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import ClockDep, RepositoriesDep, RequestContextDep
from app.api.envelope import SuccessEnvelope
from app.api.schemas import JobOut, ServiceRequestOut, success
from app.core.ids import ServiceRequestId
from app.domain.enums import ServiceRequestStatus
from app.services import service_request_service
from app.services.service_request_service import ConfirmJob

router = APIRouter(prefix="/service-requests", tags=["service requests"])


@router.get("")
def list_service_requests(
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    status: ServiceRequestStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SuccessEnvelope[list[ServiceRequestOut]]:
    found = service_request_service.list_requests(ctx, repos, status=status, limit=limit)
    return success(ctx, [ServiceRequestOut.model_validate(r) for r in found])


@router.get("/{service_request_id}")
def get_service_request(
    service_request_id: ServiceRequestId, ctx: RequestContextDep, repos: RepositoriesDep
) -> SuccessEnvelope[ServiceRequestOut]:
    request = service_request_service.get_request(ctx, repos, service_request_id)
    return success(ctx, ServiceRequestOut.model_validate(request))


@router.post("/{service_request_id}/job", status_code=201)
def create_job_for_request(
    service_request_id: ServiceRequestId,
    body: ConfirmJob,
    response: Response,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
) -> SuccessEnvelope[JobOut]:
    """Confirm a request as a job for the chosen customer and asset. If the request already has a
    job, that job is returned (200) and nothing new is created."""
    creation = service_request_service.confirm_job(ctx, repos, clock(), service_request_id, body)
    if not creation.created:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
    return success(ctx, JobOut.model_validate(creation.job))
