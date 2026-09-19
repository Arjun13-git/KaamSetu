from zoneinfo import ZoneInfo

from pydantic import field_validator

from app.core.ids import BusinessId
from app.domain.base import ShortText, TimestampedModel


class Business(TimestampedModel):
    business_id: BusinessId
    name: ShortText
    timezone: str
    default_language: ShortText = "en"

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value!r}") from exc
        return value
