from datetime import UTC, datetime
from typing import Annotated, Any, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints, model_validator


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


# Naive datetimes are rejected; aware ones are normalized to UTC.
UtcDatetime = Annotated[datetime, AfterValidator(_ensure_utc)]

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class DomainModel(BaseModel):
    """Immutable, strict base for every domain record.

    Records are never mutated in place; ``evolve`` returns a re-validated copy so invariants
    are checked on every change.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    def evolve(self, **changes: Any) -> Self:
        return type(self).model_validate({**dict(self), **changes})


class TimestampedModel(DomainModel):
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def _updated_not_before_created(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
