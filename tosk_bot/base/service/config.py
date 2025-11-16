from functools import lru_cache
from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings for tosk-bot base service.
    - TELEGRAM_API_TOKEN --- Telegram bot API token
    - RABBITMQ_URL       --- RabbitMQ URL
    env_prefix: TOSK_BOT_BASE_
    """
    telegram_api_token: str = Field(..., description="Telegram bot API token")
    rabbitmq_url: AnyUrl = Field(..., description="RabbitMQ connection URL")

    # TODO configure tgio.Input and tgil.Output instances
    topic_exchange_timeout: float = Field(1.0, description="Timeout for bus message accept")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TOSK_BOT_BASE_",
        extra="ignore",
    )


# mimic lazy evaluation to avoid initializing settings on import
# needed for tests (import -> init -> test -> clear cache (deinit))
@lru_cache(maxsize=1)
def get_settings():
    return Settings()
