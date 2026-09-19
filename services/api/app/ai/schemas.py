"""The structured record the model is asked to produce, and what is stored about an extraction.

This is the single schema for intake extraction. The tool definition sent to the model and the
published JSON Schema in ``ai/schemas`` are generated from it, and the model's answer is accepted
only if it validates against it. Unknown information is ``null`` (or an ``unknown`` enum value),
never a guess.
"""

import copy
import datetime as dt
import json
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from app.domain.base import DomainModel, LongText, ShortText
from app.domain.enums import AssetType, ServiceType, Urgency

SCHEMA_VERSION = "intake_extraction.v1"


class Intent(StrEnum):
    SERVICE_REQUEST = "service_request"
    INFORMATION_REQUEST = "information_request"
    FOLLOW_UP = "follow_up"
    CANCELLATION = "cancellation"
    STATUS_QUERY = "status_query"
    UNKNOWN = "unknown"


class Source(StrEnum):
    """Where a field's value came from."""

    EXPLICIT_TEXT = "explicit_text"
    IMAGE = "image"
    CONVERSATION_CONTEXT = "conversation_context"
    RETRIEVED_HISTORY = "retrieved_history"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


SOURCE_FIELDS = (
    "service_type",
    "customer_reference",
    "asset.type",
    "asset.brand",
    "asset.model",
    "problem.description",
    "problem.urgency",
    "problem.symptoms",
    "time_preference",
)


class AssetMention(DomainModel):
    type: AssetType
    brand: ShortText | None
    model: ShortText | None


class ProblemMention(DomainModel):
    """What the customer reported. Symptoms as stated; never a diagnosis of the cause."""

    description: LongText | None
    urgency: Urgency | None
    symptoms: list[ShortText] = Field(default_factory=list, max_length=10)


class TimePreference(DomainModel):
    """A preferred visit time in the business's local time; absent parts are ``null``."""

    date: dt.date | None = None
    start: dt.time | None = None
    end: dt.time | None = None


class Confidence(DomainModel):
    overall: float = Field(ge=0, le=1)
    asset: float = Field(ge=0, le=1)
    problem: float = Field(ge=0, le=1)
    schedule: float = Field(ge=0, le=1)


class IntakeExtraction(DomainModel):
    intent: Intent
    service_type: ServiceType
    customer_reference: ShortText | None
    asset: AssetMention
    problem: ProblemMention
    time_preference: TimePreference
    confidence: Confidence
    missing_information: list[ShortText] = Field(default_factory=list, max_length=20)
    sources: dict[str, Source] = Field(default_factory=dict)

    @field_validator("sources", mode="before")
    @classmethod
    def _keep_known_fields_only(cls, value: Any) -> Any:
        """Provenance for a field we do not have is dropped; a bad *value* still fails."""
        if isinstance(value, dict):
            return {k: v for k, v in value.items() if k in SOURCE_FIELDS}
        return value


class StoredExtraction(DomainModel):
    """What is persisted on the ServiceRequest: the validated extraction plus how it was made and
    what deterministic guards changed. No raw prompt or model text is kept."""

    schema_version: str = SCHEMA_VERSION
    prompt_version: str
    model_id: str
    data: IntakeExtraction
    safety_concern: bool = False
    image_supplied: bool = False
    warnings: list[ShortText] = Field(default_factory=list, max_length=20)


def tool_input_schema() -> dict[str, Any]:
    """JSON Schema for ``IntakeExtraction`` with every ``$ref`` inlined, so any tool-calling model
    reads one self-contained object."""
    schema = IntakeExtraction.model_json_schema()
    definitions: dict[str, Any] = schema.pop("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                return inline(copy.deepcopy(definitions[name]))
            return {key: inline(value) for key, value in node.items()}
        if isinstance(node, list):
            return [inline(item) for item in node]
        return node

    inlined: dict[str, Any] = inline(schema)
    return inlined


if __name__ == "__main__":  # regenerate ai/schemas/intake_extraction.v1.json
    print(json.dumps(tool_input_schema(), indent=2, ensure_ascii=False))
