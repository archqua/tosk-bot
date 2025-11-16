from functools import lru_cache
from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings for tosk-bot base service.
    - RABBITMQ_URL       --- RabbitMQ URL
    env_prefix: TOSK_BOT_EXT_PING_
    """

    rabbitmq_url: AnyUrl = Field(..., description="RabbitMQ connection URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TOSK_BOT_EXT_PING_",
        extra="ignore",
    )


# mimic lazy evaluation to avoid initializing settings on import
# needed for tests (import -> init -> test -> clear cache (deinit))
@lru_cache(maxsize=1)
def get_settings():
    return Settings()
