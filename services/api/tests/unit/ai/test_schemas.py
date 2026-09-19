import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.schemas import (
    SCHEMA_VERSION,
    IntakeExtraction,
    Source,
    StoredExtraction,
    tool_input_schema,
)
from tests.ai_support import valid_extraction

PUBLISHED = Path(__file__).resolve().parents[5] / "ai" / "schemas" / "intake_extraction.v1.json"


def test_a_valid_answer_parses_with_unknowns_left_unknown() -> None:
    data = IntakeExtraction.model_validate(valid_extraction())

    assert data.asset.brand == "LG" and data.asset.model is None
    assert data.customer_reference is None
    assert data.problem.urgency is None
    assert data.time_preference.date is None


def test_dates_and_times_are_parsed() -> None:
    answer = valid_extraction(time_preference={"date": "2026-09-20", "start": "17:00", "end": None})

    preference = IntakeExtraction.model_validate(answer).time_preference

    assert preference.date == dt.date(2026, 9, 20) and preference.start == dt.time(17, 0)


@pytest.mark.parametrize(
    "mutation",
    [
        {"intent": "buy_something"},
        {"service_type": "exorcism"},
        {"asset": {"type": "spaceship", "brand": None, "model": None}},
        {"problem": {"description": "x", "urgency": "medium", "symptoms": []}},
        {"time_preference": {"date": "tomorrow", "start": None, "end": None}},
        {"confidence": {"overall": 1.4, "asset": 0.5, "problem": 0.5, "schedule": 0.5}},
        {"confidence": {"overall": 0.5}},
        {"sources": {"asset.type": "made_up_source"}},
    ],
)
def test_out_of_contract_answers_are_rejected(mutation: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        IntakeExtraction.model_validate(valid_extraction(**mutation))


@pytest.mark.parametrize("field", ["intent", "service_type", "asset", "problem", "confidence"])
def test_required_parts_cannot_be_omitted(field: str) -> None:
    answer = valid_extraction()
    del answer[field]

    with pytest.raises(ValidationError):
        IntakeExtraction.model_validate(answer)


def test_the_model_cannot_add_fields_such_as_identity_or_actions() -> None:
    for extra in ({"business_id": "bus_x"}, {"customer_id": "cus_x"}, {"assign_to": "tec_x"}):
        with pytest.raises(ValidationError):
            IntakeExtraction.model_validate(valid_extraction(**extra))
    nested = valid_extraction(asset={"type": "printer", "brand": None, "model": None, "price": 5})
    with pytest.raises(ValidationError):
        IntakeExtraction.model_validate(nested)


def test_provenance_for_unknown_fields_is_dropped_but_bad_values_still_fail() -> None:
    answer = valid_extraction(sources={"asset.type": "image", "invented.field": "explicit_text"})

    sources = IntakeExtraction.model_validate(answer).sources

    assert sources == {"asset.type": Source.IMAGE}


def test_the_tool_schema_is_self_contained_and_strict() -> None:
    schema = tool_input_schema()

    assert "$defs" not in schema and "$ref" not in json.dumps(schema)
    assert schema["additionalProperties"] is False
    assert {"intent", "service_type", "asset", "problem", "confidence"} <= set(schema["required"])
    assert "spaceship" not in schema["properties"]["asset"]["properties"]["type"]["enum"]
    assert "air_conditioner" in schema["properties"]["asset"]["properties"]["type"]["enum"]
    assert schema["properties"]["problem"]["properties"]["urgency"]["anyOf"][0]["enum"] == [
        "low",
        "normal",
        "high",
        "safety_critical",
    ]


def test_the_published_json_schema_is_current() -> None:
    """Regenerate with: python -m app.ai.schemas > ai/schemas/intake_extraction.v1.json"""
    assert json.loads(PUBLISHED.read_text()) == tool_input_schema()


def test_stored_extraction_round_trips_through_json() -> None:
    stored = StoredExtraction(
        prompt_version="intake_v1",
        model_id="some-model",
        data=IntakeExtraction.model_validate(valid_extraction()),
        safety_concern=True,
        warnings=["a warning"],
    )

    restored = StoredExtraction.model_validate(stored.model_dump(mode="json"))

    assert restored == stored and restored.schema_version == SCHEMA_VERSION
