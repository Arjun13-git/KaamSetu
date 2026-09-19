from pydantic import Field, field_validator

from app.core.ids import AttachmentId, BusinessId
from app.domain.base import DomainModel, ShortText, UtcDatetime
from app.domain.enums import AttachmentOwnerType


class Attachment(DomainModel):
    """Metadata for a binary object held in object storage. Untrusted until validated."""

    attachment_id: AttachmentId
    business_id: BusinessId
    owner_type: AttachmentOwnerType
    owner_id: ShortText
    object_key: str = Field(min_length=1, max_length=512)
    content_type: ShortText
    size: int = Field(gt=0)
    created_at: UtcDatetime

    @field_validator("object_key")
    @classmethod
    def _safe_key(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("object_key must be a relative path without '..' segments")
        return value
