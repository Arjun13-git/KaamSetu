import datetime as dt

import pytest

from app.ai.guards import apply_guards, detect_safety_concern
from app.ai.schemas import IntakeExtraction, Source
from app.domain.enums import Urgency
from tests.ai_support import valid_extraction

TODAY = dt.date(2026, 9, 19)


def _guard(text: str = "AC not cooling", **overrides):
    return apply_guards(
        IntakeExtraction.model_validate(valid_extraction(**overrides)), text=text, today=TODAY
    )


class TestDates:
    def test_a_date_in_the_past_is_dropped_and_reported_as_missing(self) -> None:
        result = _guard(time_preference={"date": "2026-09-18", "start": "17:00", "end": None})

        assert result.data.time_preference.date is None
        assert result.data.time_preference.start is None
        assert "time_preference" in result.data.missing_information
        assert any("in the past" in w for w in result.warnings)

    @pytest.mark.parametrize("day", ["2026-09-19", "2026-09-20", "2027-01-01"])
    def test_today_and_future_dates_are_kept(self, day: str) -> None:
        result = _guard(time_preference={"date": day, "start": "17:00", "end": None})

        assert result.data.time_preference.date == dt.date.fromisoformat(day)
        assert result.warnings == []

    def test_an_end_time_not_after_the_start_is_dropped(self) -> None:
        result = _guard(time_preference={"date": "2026-09-20", "start": "17:00", "end": "16:00"})

        assert result.data.time_preference.start == dt.time(17, 0)
        assert result.data.time_preference.end is None


class TestSafety:
    @pytest.mark.parametrize(
        "text",
        [
            "AC is sparking when I switch it on",
            "burning smell from the fridge",
            "There is smoke coming from the washing machine",
            "I got an electric shock touching it",
            "exposed wires near the switch",
            "AC se chingari nikal rahi hai",
            "kuch jalne ki smell aa rahi hai",
            "there might be a fire",
        ],
    )
    def test_dangerous_wording_raises_urgency_to_safety_critical(self, text: str) -> None:
        result = _guard(text=text)

        assert result.safety_concern
        assert result.data.problem.urgency is Urgency.SAFETY_CRITICAL
        assert result.data.sources["problem.urgency"] is Source.INFERRED
        assert any("Safety-related" in w for w in result.warnings)

    @pytest.mark.parametrize(
        "text",
        ["AC not cooling", "Bhaiya LG AC thanda nahi kar raha", "water leaking from the purifier"],
    )
    def test_ordinary_requests_are_left_alone(self, text: str) -> None:
        result = _guard(text=text)

        assert not result.safety_concern and not detect_safety_concern(text)
        assert result.data.problem.urgency is None and result.warnings == []

    def test_the_model_flagging_danger_is_respected_and_never_lowered(self) -> None:
        problem = {"description": "x", "urgency": "safety_critical", "symptoms": []}

        result = _guard(text="AC noise", problem=problem)

        assert result.safety_concern
        assert result.data.problem.urgency is Urgency.SAFETY_CRITICAL
        assert result.warnings == []

    def test_high_urgency_is_raised_but_never_lowered(self) -> None:
        problem = {"description": "x", "urgency": "high", "symptoms": []}

        assert _guard(text="fridge sparks", problem=problem).data.problem.urgency is (
            Urgency.SAFETY_CRITICAL
        )
        assert _guard(text="fridge noisy", problem=problem).data.problem.urgency is Urgency.HIGH


def test_guards_do_not_invent_or_remove_anything_else() -> None:
    result = _guard()

    assert result.data.asset.model is None and result.data.asset.brand == "LG"
    assert result.data.customer_reference is None
    assert result.data.problem.description == "AC not cooling"
