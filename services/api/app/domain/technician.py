from pydantic import Field, field_validator

from app.core.ids import BusinessId, TechnicianId
from app.domain.base import ShortText, TimestampedModel
from app.domain.normalization import normalize_phone


class Technician(TimestampedModel):
    technician_id: TechnicianId
    business_id: BusinessId
    name: ShortText
    phone: str | None = None
    skills: list[ShortText] = Field(default_factory=list, max_length=50)
    active: bool = True

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_phone(value)
        if normalized is None:
            raise ValueError("phone number is not valid")
        return normalized
