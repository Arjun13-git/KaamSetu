import logging

from app.ai.bedrock import BedrockLLM
from app.ai.extractor import IntakeExtractor
from app.ai.provider import StructuredLLM, UnavailableLLM
from app.core.config import Settings

logger = logging.getLogger("kaamsetu.ai")


def build_extractor(settings: Settings) -> IntakeExtractor:
    """Select the language-model provider. Only Bedrock is implemented; anything else yields an
    extractor whose every call fails, which sends intake down the manual path."""
    llm: StructuredLLM
    if settings.llm_provider == "bedrock":
        assert settings.llm_model  # enforced by Settings
        llm = BedrockLLM.create(
            model_id=settings.llm_model,
            region=settings.aws_region,
            profile=settings.aws_profile,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    else:
        logger.warning(
            "LLM provider %r is not available; intake will be manual", settings.llm_provider
        )
        llm = UnavailableLLM(f"LLM provider {settings.llm_provider!r} is not available")
    return IntakeExtractor(
        llm,
        model_id=settings.llm_model or settings.llm_provider,
        max_retries=settings.ai_max_retries,
    )
