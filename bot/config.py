from pydantic import BaseSettings, Field
from pydantic_settings import SettingsConfigDict
from typing import List


class AppConfig(BaseSettings):
    api_token: str = Field(..., description="Telegram bot API token")
    debug: bool = Field(default=False, description="Enable debug mode")
    allowed_hosts: List[str] = Field(default=["localhost"], description="Allowed hosts")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = AppConfig()
