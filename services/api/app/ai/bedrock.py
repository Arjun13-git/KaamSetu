"""Amazon Bedrock adapter using the Converse API with a forced tool call, so the model must answer
with a single structured object. The adapter only calls the model; it never touches storage."""

import logging
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.ai.provider import ImageInput
from app.core.errors import AiInvalidOutputError, AiUnavailableError

logger = logging.getLogger("kaamsetu.ai")

_MAX_OUTPUT_TOKENS = 1500


class BedrockLLM:
    def __init__(self, client: Any, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    @classmethod
    def create(
        cls,
        *,
        model_id: str,
        region: str | None,
        profile: str | None,
        timeout_seconds: float,
    ) -> "BedrockLLM":
        """Credentials come from the standard AWS chain (for Lambda, the function's role). Retries
        are handled by the caller so the total time stays within its budget."""
        session = boto3.Session(profile_name=profile, region_name=region)
        client = session.client(
            "bedrock-runtime",
            config=Config(
                connect_timeout=3,
                read_timeout=timeout_seconds,
                retries={"max_attempts": 1, "mode": "standard"},
            ),
        )
        return cls(client, model_id)

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
        content: list[dict[str, Any]] = [{"text": user_text}]
        if image is not None:
            content.append({"image": {"format": image.format, "source": {"bytes": image.data}}})

        started = time.monotonic()
        try:
            response = self._client.converse(
                modelId=self._model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": content}],
                toolConfig={
                    "tools": [
                        {
                            "toolSpec": {
                                "name": tool_name,
                                "description": tool_description,
                                "inputSchema": {"json": schema},
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": tool_name}},
                },
                inferenceConfig={"maxTokens": _MAX_OUTPUT_TOKENS, "temperature": 0},
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "unknown"))
            detail = str(exc.response.get("Error", {}).get("Message", ""))[:400]
            # The service's message goes to the private log for operators, never to the client.
            logger.error("Bedrock call failed: %s: %s", code, detail)
            raise AiUnavailableError("The AI service is unavailable") from exc
        except BotoCoreError as exc:
            logger.error("Bedrock call failed: %s", type(exc).__name__)
            raise AiUnavailableError("The AI service is unavailable") from exc

        usage = response.get("usage", {})
        logger.info(
            "Bedrock call: model=%s latency_ms=%d input_tokens=%s output_tokens=%s stop=%s",
            self._model_id,
            int((time.monotonic() - started) * 1000),
            usage.get("inputTokens"),
            usage.get("outputTokens"),
            response.get("stopReason"),
        )
        return _tool_input(response, tool_name)


def _tool_input(response: dict[str, Any], tool_name: str) -> dict[str, Any]:
    if response.get("stopReason") == "max_tokens":
        raise AiInvalidOutputError("The AI answer was cut off")
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    for block in blocks:
        tool_use = block.get("toolUse")
        if tool_use and tool_use.get("name") == tool_name:
            answer = tool_use.get("input")
            if isinstance(answer, dict):
                return answer
    raise AiInvalidOutputError("The AI did not return structured output")
