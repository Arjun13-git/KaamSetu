"""The Bedrock adapter's one narrow repair: the string "null" where the schema allows JSON null.

Scope is deliberately tiny. Only the exact literal ``"null"``, only where the schema declares the
position nullable. Everything else must come through untouched so validation still sees it.
"""

import copy
import datetime as dt
import logging
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.bedrock import BedrockLLM, normalize_null_literals
from app.ai.extractor import TOOL_NAME, IntakeExtractor
from app.ai.schemas import IntakeExtraction, tool_input_schema
from app.core.errors import AiInvalidOutputError
from tests.ai_support import FakeBedrockClient, tool_response, valid_extraction

SCHEMA = tool_input_schema()


def _normalize(answer: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    return normalize_null_literals(answer, SCHEMA)


def _with(**parts: Any) -> dict[str, Any]:
    return valid_extraction(**parts)


class TestNullableFieldsAcceptTheLiteral:
    @pytest.mark.parametrize(
        ("answer", "path"),
        [
            (
                _with(time_preference={"date": "null", "start": None, "end": None}),
                "time_preference.date",
            ),
            (
                _with(time_preference={"date": None, "start": "null", "end": None}),
                "time_preference.start",
            ),
            (
                _with(time_preference={"date": None, "start": None, "end": "null"}),
                "time_preference.end",
            ),
            (_with(asset={"type": "printer", "brand": "null", "model": None}), "asset.brand"),
            (_with(asset={"type": "printer", "brand": None, "model": "null"}), "asset.model"),
            (_with(customer_reference="null"), "customer_reference"),
            (
                _with(problem={"description": "null", "urgency": None, "symptoms": []}),
                "problem.description",
            ),
            (
                _with(problem={"description": "x", "urgency": "null", "symptoms": []}),
                "problem.urgency",
            ),
        ],
    )
    def test_the_literal_becomes_none_at_a_nullable_position(
        self, answer: dict[str, Any], path: str
    ) -> None:
        normalized, changed = _normalize(answer)

        assert changed == [path]
        node: Any = normalized
        for part in path.split("."):
            node = node[part]
        assert node is None

    def test_the_answer_nova_actually_produced_now_passes_validation(self) -> None:
        raw = _with(
            time_preference={"date": "null", "start": "null", "end": "null"},
            asset={"type": "air_conditioner", "brand": "null", "model": "null"},
        )
        with pytest.raises(ValidationError):
            IntakeExtraction.model_validate(raw)  # the failure being fixed

        normalized, changed = _normalize(raw)

        data = IntakeExtraction.model_validate(normalized)
        assert data.time_preference.date is None and data.asset.brand is None
        assert len(changed) == 5

    def test_the_input_is_not_modified(self) -> None:
        raw = _with(time_preference={"date": "null", "start": None, "end": None})
        before = copy.deepcopy(raw)

        _normalize(raw)

        assert raw == before


class TestNothingElseIsTouched:
    def test_a_string_in_a_field_that_cannot_be_null_stays_the_string_null(self) -> None:
        answer = _with(
            problem={"description": "x", "urgency": None, "symptoms": ["null", "noise"]},
            missing_information=["null"],
        )

        normalized, changed = _normalize(answer)

        assert normalized["problem"]["symptoms"] == ["null", "noise"]  # list items are not nullable
        assert normalized["missing_information"] == ["null"]
        assert changed == []

    def test_a_non_nullable_string_property_in_any_schema_is_left_alone(self) -> None:
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}

        normalized, changed = normalize_null_literals({"name": "null"}, schema)

        assert normalized == {"name": "null"} and changed == []

    def test_a_required_enum_saying_null_is_not_repaired_and_still_fails_validation(self) -> None:
        normalized, changed = _normalize(_with(intent="null", service_type="null"))

        assert normalized["intent"] == "null" and normalized["service_type"] == "null"
        assert changed == []
        with pytest.raises(ValidationError):
            IntakeExtraction.model_validate(normalized)

    def test_real_json_null_and_other_falsy_values_are_unchanged(self) -> None:
        answer = _with(
            customer_reference=None,
            time_preference={"date": None, "start": None, "end": None},
            missing_information=[],
            problem={"description": "", "urgency": None, "symptoms": []},
        )

        normalized, changed = _normalize(answer)

        assert normalized == answer and changed == []
        assert normalized["customer_reference"] is None
        assert normalized["time_preference"]["start"] is None

    @pytest.mark.parametrize(
        "text",
        [
            "null pointer exception on the display",
            "the value is null",
            "Nullify",
            "nullable",
            "AC shows null on screen",
            "null null",
        ],
    )
    def test_text_that_merely_contains_the_word_is_unchanged(self, text: str) -> None:
        answer = _with(
            problem={"description": text, "urgency": None, "symptoms": [text]},
            asset={"type": "computer", "brand": text, "model": None},
            customer_reference=text,
        )

        normalized, changed = _normalize(answer)

        assert normalized["problem"]["description"] == text
        assert normalized["problem"]["symptoms"] == [text]
        assert normalized["asset"]["brand"] == text
        assert normalized["customer_reference"] == text
        assert changed == []

    @pytest.mark.parametrize(
        "spelling", ["NULL", "Null", "None", "none", " null", "null ", "nil", "N/A", ""]
    )
    def test_only_the_exact_literal_qualifies(self, spelling: str) -> None:
        answer = _with(asset={"type": "printer", "brand": spelling, "model": None})

        normalized, changed = _normalize(answer)

        assert normalized["asset"]["brand"] == spelling and changed == []

    def test_keys_the_schema_does_not_define_are_not_touched(self) -> None:
        answer = _with(
            business_id="null", asset={"type": "printer", "brand": None, "model": None, "x": "null"}
        )

        normalized, changed = _normalize(answer)

        assert normalized["business_id"] == "null" and normalized["asset"]["x"] == "null"
        assert changed == []
        with pytest.raises(ValidationError):  # and validation still rejects them
            IntakeExtraction.model_validate(normalized)

    def test_no_schema_information_means_no_change(self) -> None:
        assert normalize_null_literals({"a": "null"}, {}) == ({"a": "null"}, [])


class TestThroughTheAdapter:
    def _call(self, answer: dict[str, Any]) -> tuple[dict[str, Any], FakeBedrockClient]:
        client = FakeBedrockClient(tool_response(answer, name=TOOL_NAME))
        result = BedrockLLM(client, "test.model").generate_structured(
            system="s",
            user_text="u",
            image=None,
            tool_name=TOOL_NAME,
            tool_description="d",
            schema=SCHEMA,
        )
        return result, client

    def test_the_adapter_returns_the_repaired_answer(self) -> None:
        raw = _with(time_preference={"date": "2026-09-20", "start": "null", "end": "null"})

        result, _ = self._call(raw)

        assert result["time_preference"] == {"date": "2026-09-20", "start": None, "end": None}

    def test_an_unaffected_answer_is_returned_as_it_came(self) -> None:
        raw = _with()

        result, _ = self._call(raw)

        assert result == raw

    def test_the_repair_is_logged_by_field_path_and_never_by_content(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        raw = _with(
            customer_reference="null",
            problem={"description": "AC null pointer", "urgency": None, "symptoms": []},
        )

        with caplog.at_level(logging.INFO, logger="kaamsetu.ai"):
            self._call(raw)

        logged = " ".join(r.getMessage() for r in caplog.records)
        assert "customer_reference" in logged
        assert "AC null pointer" not in logged

    def test_an_answer_that_needed_the_repair_is_now_valid_on_the_first_call(self) -> None:
        raw = _with(time_preference={"date": "null", "start": "null", "end": "null"})
        client = FakeBedrockClient(tool_response(raw, name=TOOL_NAME))
        extractor = IntakeExtractor(
            BedrockLLM(client, "test.model"), model_id="test.model", max_retries=1
        )

        stored = extractor.extract(
            text="Ramesh sir ke ghar ka AC gas refill chahiye",
            today=dt.date(2026, 9, 19),
            timezone="UTC",
        )

        assert len(client.requests) == 1  # no retry needed
        assert stored.data.time_preference.date is None

    def test_a_genuinely_invalid_answer_still_fails_after_the_repair(self) -> None:
        raw = _with(asset={"type": "spaceship", "brand": "null", "model": None})
        client = FakeBedrockClient(tool_response(raw, name=TOOL_NAME))
        extractor = IntakeExtractor(
            BedrockLLM(client, "test.model"), model_id="test.model", max_retries=0
        )

        with pytest.raises(AiInvalidOutputError):
            extractor.extract(text="x", today=dt.date(2026, 9, 19), timezone="UTC")
