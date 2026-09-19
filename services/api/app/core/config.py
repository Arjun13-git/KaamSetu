from typing import Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.ids import ActorId, BusinessId


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (and a local ``.env``).

    ``app_env`` defaults to ``production`` so a deployment that forgets to configure it fails
    closed: the development actor below is only available in ``development`` and ``test``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "production"
    app_name: str = "kaamsetu"
    log_level: str = "INFO"

    data_provider: Literal["memory", "dynamodb"] = "memory"
    dynamodb_table: str = "kaamsetu"
    dynamodb_endpoint_url: str | None = None
    aws_region: str | None = None
    aws_profile: str | None = None

    # Development-only identity. Tenant identity is always decided server-side; it is never read
    # from a request header, query string or body.
    dev_business_id: BusinessId = "bus_demo"
    dev_actor_id: ActorId = "usr_dev"

    @field_validator("dynamodb_endpoint_url", "aws_region", "aws_profile", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _production_needs_durable_storage(self) -> Self:
        if self.app_env == "production" and self.data_provider == "memory":
            raise ValueError("DATA_PROVIDER=memory is not allowed when APP_ENV=production")
        return self

    @property
    def dev_actor_enabled(self) -> bool:
        return self.app_env in ("development", "test")
