"""Turns a customer message (and optional photo) into a validated, guarded extraction.

The model is untrusted: its answer is accepted only if it passes schema validation, is retried a
bounded number of times when it does not, and is then checked by deterministic guards. Nothing in
this module reads or writes storage.
"""

import datetime as dt
import json
import logging
from importlib import resources

from pydantic import ValidationError

from app.ai.guards import apply_guards
from app.ai.provider import ImageInput, StructuredLLM
from app.ai.schemas import IntakeExtraction, StoredExtraction, tool_input_schema
from app.core.errors import AiInvalidOutputError, AiUnavailableError

logger = logging.getLogger("kaamsetu.ai")

PROMPT_VERSION = "intake_v1"
TOOL_NAME = "record_service_request"
TOOL_DESCRIPTION = (
    "Record what the customer's message says about a service need. Unknown information must be "
    "null; never guess."
)


def load_prompt(version: str = PROMPT_VERSION) -> str:
    return resources.files("app.ai.prompts").joinpath(f"{version}.md").read_text(encoding="utf-8")


class IntakeExtractor:
    def __init__(self, llm: StructuredLLM, *, model_id: str, max_retries: int = 1) -> None:
        self._llm = llm
        self._model_id = model_id
        self._max_retries = max_retries
        self._prompt = load_prompt()
        self._schema = tool_input_schema()

    def extract(
        self, *, text: str, today: dt.date, timezone: str, image: ImageInput | None = None
    ) -> StoredExtraction:
        """Raises ``AiUnavailableError`` or ``AiInvalidOutputError`` after the last attempt."""
        feedback: str | None = None
        failure: AiUnavailableError | AiInvalidOutputError | None = None

        for attempt in range(1 + self._max_retries):
            try:
                answer = self._llm.generate_structured(
                    system=self._prompt,
                    user_text=_user_text(text, today, timezone, feedback),
                    image=image,
                    tool_name=TOOL_NAME,
                    tool_description=TOOL_DESCRIPTION,
                    schema=self._schema,
                )
                data = IntakeExtraction.model_validate(answer)
            except ValidationError as exc:
                fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
                logger.warning(
                    "Model output failed validation (attempt %d): %s", attempt + 1, fields
                )
                feedback = "Fields rejected by schema validation: " + ", ".join(fields)
                failure = AiInvalidOutputError("The AI answer did not match the required format")
            except (AiUnavailableError, AiInvalidOutputError) as exc:
                logger.warning("Model call failed (attempt %d): %s", attempt + 1, exc.code.value)
                failure = exc
            else:
                guarded = apply_guards(data, text=text, today=today)
                return StoredExtraction(
                    prompt_version=PROMPT_VERSION,
                    model_id=self._model_id,
                    data=guarded.data,
                    safety_concern=guarded.safety_concern,
                    image_supplied=image is not None,
                    warnings=guarded.warnings,
                )

        assert failure is not None
        raise failure


def _user_text(text: str, today: dt.date, timezone: str, feedback: str | None) -> str:
    """The message travels as a JSON string, with angle brackets escaped (``\\u003c``), so nothing
    in it can close the surrounding tags. The escaped form decodes to exactly the original text."""
    lines = [
        "Context (trusted):",
        f"today: {today.isoformat()} ({today.strftime('%A')})",
        f"timezone: {timezone}",
        "",
        "<customer_message>",
        _quoted(text),
        "</customer_message>",
    ]
    if feedback:
        lines += ["", f"Your previous answer was not accepted. {feedback}. Answer again."]
    return "\n".join(lines)


def _quoted(text: str) -> str:
    return json.dumps(text, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
