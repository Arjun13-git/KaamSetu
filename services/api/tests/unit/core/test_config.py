import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.providers.persistence.dynamodb.repositories import DynamoJobRepository
from app.providers.persistence.factory import build_repositories
from app.providers.persistence.memory import InMemoryJobRepository


def _load(**env: str) -> Settings:
    return Settings(_env_file=None, **env)  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "APP_ENV",
        "DATA_PROVIDER",
        "DYNAMODB_TABLE",
        "DYNAMODB_ENDPOINT_URL",
        "AWS_REGION",
        "DEV_BUSINESS_ID",
    ):
        monkeypatch.delenv(name, raising=False)


def test_an_unconfigured_deployment_fails_closed() -> None:
    with pytest.raises(ValidationError, match="not allowed when APP_ENV=production"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_production_requires_durable_storage() -> None:
    with pytest.raises(ValidationError):
        _load(app_env="production", data_provider="memory")
    assert _load(app_env="production", data_provider="dynamodb").data_provider == "dynamodb"


def test_development_actor_is_limited_to_development_and_test() -> None:
    assert _load(app_env="development").dev_actor_enabled
    assert _load(app_env="test").dev_actor_enabled
    assert not _load(app_env="production", data_provider="dynamodb").dev_actor_enabled


def test_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATA_PROVIDER", "dynamodb")
    monkeypatch.setenv("DYNAMODB_TABLE", "kaamsetu-dev")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.dynamodb_table == "kaamsetu-dev"
    assert settings.aws_region == "eu-west-1"


def test_blank_optional_values_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNAMODB_ENDPOINT_URL", "")
    monkeypatch.setenv("AWS_REGION", "  ")

    settings = _load(app_env="development")

    assert settings.dynamodb_endpoint_url is None
    assert settings.aws_region is None


def test_the_development_identity_must_use_valid_id_formats() -> None:
    with pytest.raises(ValidationError):
        _load(app_env="development", dev_business_id="not-a-business-id")


def test_the_provider_factory_selects_the_adapter() -> None:
    memory = build_repositories(_load(app_env="development", data_provider="memory"))
    dynamodb = build_repositories(
        _load(app_env="development", data_provider="dynamodb", aws_region="ap-south-1")
    )

    assert isinstance(memory.jobs, InMemoryJobRepository)
    assert isinstance(dynamodb.jobs, DynamoJobRepository)
