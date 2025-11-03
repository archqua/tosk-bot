import sys
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class AppConfig(BaseSettings):
    telegram_api_token: str = Field(..., description="Telegram bot API token")
    debug: bool = Field(default=False, description="Enable debug mode")
    allowed_hosts: List[str] = Field(default=["localhost"], description="Allowed hosts")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TOSK_BOT_",
        extra="ignore",
    )


# Lazy module-level settings property with cached single instance and deleter for tests
_module = sys.modules[__name__]


def _get_settings():
    if not hasattr(_module, "_settings_cache"):
        _module._settings_cache = AppConfig()
    return _module._settings_cache


def _del_settings():
    """Only use for tests"""
    if hasattr(_module, "_settings_cache"):
        del _module._settings_cache


class _SettingsAccessor:
    def __get__(self, instance, owner):
        return _get_settings()

    def __delete__(self, instance):
        """Only use for tests"""
        _del_settings()


# Install property on module as settings attribute
setattr(sys.modules[__name__], "settings", _SettingsAccessor())
