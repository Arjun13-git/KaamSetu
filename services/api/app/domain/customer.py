from pydantic import field_validator

from app.core.ids import BusinessId, CustomerId
from app.domain.base import LongText, ShortText, TimestampedModel
from app.domain.normalization import normalize_phone


class Customer(TimestampedModel):
    customer_id: CustomerId
    business_id: BusinessId
    name: ShortText
    phone: str | None = None
    email: ShortText | None = None
    address: LongText | None = None
    preferred_language: ShortText | None = None
    notes: LongText | None = None

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_phone(value)
        if normalized is None:
            raise ValueError("phone number is not valid")
        return normalized
