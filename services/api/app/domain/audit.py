from datetime import datetime

from pydantic import Field

from app.core.context import RequestContext
from app.core.ids import ActorId, AuditId, BusinessId, IdPrefix, RequestId, new_id
from app.domain.base import DomainModel, ShortText, UtcDatetime
from app.domain.enums import AuditAction, AuditEntityType


class AuditEvent(DomainModel):
    """Append-only record of a mutation. ``metadata`` holds scalar identifiers/status values
    only; raw customer text and other PII do not belong here."""

    audit_id: AuditId
    business_id: BusinessId
    actor_id: ActorId
    action: AuditAction
    entity_type: AuditEntityType
    entity_id: ShortText
    timestamp: UtcDatetime
    request_id: RequestId
    metadata: dict[str, str | int | bool | None] = Field(default_factory=dict)


def build_audit(
    ctx: RequestContext,
    now: datetime,
    action: AuditAction,
    entity_type: AuditEntityType,
    entity_id: str,
    metadata: dict[str, str | int | bool | None] | None = None,
) -> AuditEvent:
    """Create the audit record for a mutation performed under ``ctx``."""
    return AuditEvent(
        audit_id=new_id(IdPrefix.AUDIT),
        business_id=ctx.business_id,
        actor_id=ctx.actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        timestamp=now,
        request_id=ctx.request_id,
        metadata=metadata or {},
    )
