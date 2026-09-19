from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.api.deps import RequestIdDep
from app.api.envelope import SuccessEnvelope

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health")
def health(request_id: RequestIdDep) -> SuccessEnvelope[HealthStatus]:
    """Liveness only: it proves the process is serving, not that storage is reachable."""
    return SuccessEnvelope(
        data=HealthStatus(status="ok", version=__version__), request_id=request_id
    )
