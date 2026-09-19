from fastapi import APIRouter

from app.api.deps import ClockDep, RepositoriesDep, RequestContextDep
from app.api.envelope import SuccessEnvelope
from app.api.schemas import TechnicianOut, success
from app.core.ids import TechnicianId
from app.services import technician_service
from app.services.technician_service import NewTechnician

router = APIRouter(prefix="/technicians", tags=["technicians"])


@router.post("", status_code=201)
def create_technician(
    body: NewTechnician, ctx: RequestContextDep, repos: RepositoriesDep, clock: ClockDep
) -> SuccessEnvelope[TechnicianOut]:
    technician = technician_service.create_technician(ctx, repos, clock(), body)
    return success(ctx, TechnicianOut.model_validate(technician))


@router.get("")
def list_technicians(
    ctx: RequestContextDep, repos: RepositoriesDep, active_only: bool = False
) -> SuccessEnvelope[list[TechnicianOut]]:
    found = technician_service.list_technicians(ctx, repos, active_only=active_only)
    return success(ctx, [TechnicianOut.model_validate(t) for t in found])


@router.get("/{technician_id}")
def get_technician(
    technician_id: TechnicianId, ctx: RequestContextDep, repos: RepositoriesDep
) -> SuccessEnvelope[TechnicianOut]:
    technician = technician_service.get_technician(ctx, repos, technician_id)
    return success(ctx, TechnicianOut.model_validate(technician))
