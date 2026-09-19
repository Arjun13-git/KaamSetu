from pydantic import Field

from app.core.ids import ActorId, AuditId, BusinessId, RequestId
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
