from typing import Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.ids import ActorId, BusinessId

MIN_DEMO_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (and a local ``.env``).

    ``app_env`` defaults to ``production`` so a deployment that forgets to configure it fails
    closed. How callers are identified depends on it:

    - ``development`` / ``test``: the fixed identity below, no credentials.
    - ``demo``: the same fixed identity, but only for callers presenting ``demo_api_key``.
    - ``production``: no caller is accepted until real authentication exists.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "demo", "production"] = "production"
    app_name: str = "kaamsetu"
    log_level: str = "INFO"

    data_provider: Literal["memory", "dynamodb"] = "memory"
    dynamodb_table: str = "kaamsetu"
    dynamodb_endpoint_url: str | None = None
    aws_region: str | None = None
    aws_profile: str | None = None

    # The fixed identity used in development, test and demo. Tenant identity is always decided
    # server-side; it is never read from a request header, query string or body.
    dev_business_id: BusinessId = "bus_demo"
    dev_actor_id: ActorId = "usr_dev"

    # Shared secret for ``app_env=demo``. Presented in the ``X-Demo-Key`` header, it authorizes a
    # caller as the fixed identity above and nothing else. It never selects a tenant.
    demo_api_key: SecretStr | None = None

    @field_validator("dynamodb_endpoint_url", "aws_region", "aws_profile", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("demo_api_key", mode="before")
    @classmethod
    def _blank_key_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _deployed_environments_need_durable_storage(self) -> Self:
        if self.app_env in ("demo", "production") and self.data_provider == "memory":
            raise ValueError(f"DATA_PROVIDER=memory is not allowed when APP_ENV={self.app_env}")
        return self

    @model_validator(mode="after")
    def _demo_needs_a_strong_key(self) -> Self:
        if self.app_env == "demo":
            key = self.demo_api_key.get_secret_value() if self.demo_api_key else ""
            if len(key) < MIN_DEMO_KEY_LENGTH:
                raise ValueError(
                    f"APP_ENV=demo requires a DEMO_API_KEY of at least {MIN_DEMO_KEY_LENGTH} chars"
                )
        return self

    @property
    def dev_actor_enabled(self) -> bool:
        return self.app_env in ("development", "test")

    @property
    def demo_actor_enabled(self) -> bool:
        return self.app_env == "demo"
