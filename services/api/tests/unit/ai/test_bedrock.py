import logging
from typing import Any

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from pydantic import ValidationError

from app.ai.bedrock import BedrockLLM
from app.ai.factory import build_extractor
from app.ai.provider import ImageInput
from app.core.config import Settings
from app.core.errors import AiInvalidOutputError, AiUnavailableError

MODEL = "test.model-id"
SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}}


class FakeBedrockClient:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self._response = response
        self.requests: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _tool_response(answer: dict[str, Any], name: str = "record") -> dict[str, Any]:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"toolUse": {"name": name, "input": answer}}],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 100, "outputTokens": 50},
    }


def _call(client: FakeBedrockClient, image: ImageInput | None = None) -> dict[str, Any]:
    return BedrockLLM(client, MODEL).generate_structured(
        system="SYSTEM PROMPT",
        user_text="hello",
        image=image,
        tool_name="record",
        tool_description="Record it",
        schema=SCHEMA,
    )


def test_the_request_forces_one_tool_with_the_schema_and_no_randomness() -> None:
    client = FakeBedrockClient(_tool_response({"x": "y"}))

    answer = _call(client)

    request = client.requests[0]
    assert answer == {"x": "y"}
    assert request["modelId"] == MODEL
    assert request["system"] == [{"text": "SYSTEM PROMPT"}]
    assert request["messages"] == [{"role": "user", "content": [{"text": "hello"}]}]
    assert request["toolConfig"]["toolChoice"] == {"tool": {"name": "record"}}
    (tool,) = request["toolConfig"]["tools"]
    assert tool["toolSpec"]["inputSchema"] == {"json": SCHEMA}
    assert request["inferenceConfig"]["temperature"] == 0


def test_an_image_is_sent_as_an_image_block_with_its_bytes() -> None:
    client = FakeBedrockClient(_tool_response({"x": "y"}))
    photo = ImageInput(format="png", data=b"\x89PNG-bytes")

    _call(client, image=photo)

    content = client.requests[0]["messages"][0]["content"]
    assert content[1] == {"image": {"format": "png", "source": {"bytes": b"\x89PNG-bytes"}}}


@pytest.mark.parametrize(
    "code", ["ThrottlingException", "ModelTimeoutException", "AccessDeniedException"]
)
def test_service_errors_become_a_generic_unavailable_error(
    code: str, caplog: pytest.LogCaptureFixture
) -> None:
    error = ClientError(
        {"Error": {"Code": code, "Message": "arn:aws:bedrock:secret-detail"}}, "Converse"
    )

    with caplog.at_level(logging.ERROR), pytest.raises(AiUnavailableError) as caught:
        _call(FakeBedrockClient(error))

    assert code not in caught.value.message and "secret-detail" not in caught.value.message
    assert any(getattr(r, "aws_error", None) == code for r in caplog.records)


def test_a_network_timeout_is_unavailable() -> None:
    timeout = ReadTimeoutError(endpoint_url="https://bedrock-runtime.example")

    with pytest.raises(AiUnavailableError):
        _call(FakeBedrockClient(timeout))


@pytest.mark.parametrize(
    "response",
    [
        {"output": {"message": {"role": "assistant", "content": [{"text": "I refuse"}]}}},
        _tool_response({"x": "y"}, name="some_other_tool"),
        {**_tool_response({"x": "y"}), "stopReason": "max_tokens"},
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"toolUse": {"name": "record", "input": "text"}}],
                }
            }
        },
        {},
    ],
)
def test_answers_without_structured_output_are_invalid(response: dict[str, Any]) -> None:
    with pytest.raises(AiInvalidOutputError):
        _call(FakeBedrockClient(response))


def test_bedrock_requires_a_model_id_in_configuration() -> None:
    with pytest.raises(ValidationError, match="LLM_MODEL"):
        Settings(_env_file=None, app_env="test", llm_provider="bedrock")  # type: ignore[call-arg]


def test_an_unconfigured_provider_makes_extraction_fail_so_intake_goes_manual() -> None:
    import datetime as dt

    settings = Settings(_env_file=None, app_env="test", llm_provider="ollama")  # type: ignore[call-arg]
    extractor = build_extractor(settings)

    with pytest.raises(AiUnavailableError):
        extractor.extract(text="AC not cooling", today=dt.date(2026, 9, 19), timezone="UTC")


def test_the_model_id_comes_from_configuration_not_code() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        app_env="test",
        llm_provider="bedrock",
        llm_model="configured.model-id",
        aws_region="us-east-1",
    )

    extractor = build_extractor(settings)

    assert extractor._model_id == "configured.model-id"
