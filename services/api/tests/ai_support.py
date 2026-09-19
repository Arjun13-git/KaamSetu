"""Test doubles for the language model. Nothing here calls a real model."""

import copy
from typing import Any

from app.ai.provider import ImageInput


def valid_extraction(**overrides: Any) -> dict[str, Any]:
    """A schema-valid model answer for "AC not cooling", with any top-level part replaced."""
    answer: dict[str, Any] = {
        "intent": "service_request",
        "service_type": "repair",
        "customer_reference": None,
        "asset": {"type": "air_conditioner", "brand": "LG", "model": None},
        "problem": {"description": "AC not cooling", "urgency": None, "symptoms": ["not cooling"]},
        "time_preference": {"date": None, "start": None, "end": None},
        "confidence": {"overall": 0.9, "asset": 0.85, "problem": 0.95, "schedule": 0.0},
        "missing_information": ["asset.model"],
        "sources": {
            "asset.type": "explicit_text",
            "asset.brand": "explicit_text",
            "problem.description": "explicit_text",
        },
    }
    answer.update(copy.deepcopy(overrides))
    return answer


class ScriptedLLM:
    """Returns (or raises) the scripted answers in order, and records every call."""

    def __init__(self, *script: dict[str, Any] | Exception) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    def generate_structured(
        self,
        *,
        system: str,
        user_text: str,
        image: ImageInput | None,
        tool_name: str,
        tool_description: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "system": system,
                "user_text": user_text,
                "image": image,
                "tool_name": tool_name,
                "schema": schema,
            }
        )
        step = self._script.pop(0) if len(self._script) > 1 else self._script[0]
        if isinstance(step, Exception):
            raise step
        return copy.deepcopy(step)
