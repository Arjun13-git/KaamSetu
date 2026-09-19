from datetime import datetime

from pydantic import Field

from app.core.context import RequestContext
from app.core.ids import IdPrefix, new_id
from app.domain.audit import build_audit
from app.domain.base import DomainModel, ShortText
from app.domain.enums import AuditAction, AuditEntityType
from app.domain.repositories import Repositories
from app.domain.technician import Technician


class NewTechnician(DomainModel):
    name: ShortText
    phone: str | None = None
    skills: list[ShortText] = Field(default_factory=list, max_length=50)


def create_technician(
    ctx: RequestContext, repos: Repositories, now: datetime, data: NewTechnician
) -> Technician:
    technician = Technician(
        technician_id=new_id(IdPrefix.TECHNICIAN),
        business_id=ctx.business_id,
        created_at=now,
        updated_at=now,
        **data.model_dump(),
    )
    repos.technicians.create(technician)
    repos.audits.append(
        build_audit(
            ctx,
            now,
            AuditAction.TECHNICIAN_CREATED,
            AuditEntityType.TECHNICIAN,
            technician.technician_id,
        )
    )
    return technician


def get_technician(ctx: RequestContext, repos: Repositories, technician_id: str) -> Technician:
    return repos.technicians.get(ctx.business_id, technician_id)


def list_technicians(
    ctx: RequestContext, repos: Repositories, *, active_only: bool
) -> list[Technician]:
    return repos.technicians.list(ctx.business_id, active_only=active_only)
