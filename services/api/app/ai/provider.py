"""The interface between the application and a language model. Provider-specific code (Bedrock
today) lives behind it; nothing above this line knows which model or cloud is in use."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.core.errors import AiUnavailableError

ImageFormat = Literal["jpeg", "png", "webp", "gif"]


@dataclass(frozen=True, slots=True)
class ImageInput:
    format: ImageFormat
    data: bytes


class StructuredLLM(Protocol):
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
        """Return the model's answer as a JSON object matching ``schema``.

        Raises ``AiUnavailableError`` if the model cannot be used and ``AiInvalidOutputError`` if it
        answered without structured output. Validation against the schema is the caller's job.
        """
        ...


class UnavailableLLM:
    """Stands in when no model is configured. Every call fails, so intake falls back to manual
    entry instead of pretending to understand."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def generate_structured(self, **_: Any) -> dict[str, Any]:
        raise AiUnavailableError(self._reason)
