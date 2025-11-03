import os
import pytest
import textwrap
from pydantic import ValidationError
from pydantic_settings.exceptions import SettingsError
from bot.config import AppConfig


def test_pydantic_config_valid(tmp_path):
    test_config = textwrap.dedent(
        """
        TOSK_BOT_TELEGRAM_API_TOKEN=0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345678
        TOSK_BOT_DEBUG=true
        TOSK_BOT_ALLOWED_HOSTS=["localhost"]
        """
    ).strip()
    # Write test environment file
    env_file = tmp_path / ".env"
    env_file.write_text(test_config)

    # Load config using the env_file path override
    config = AppConfig(_env_file=str(env_file))

    assert config.telegram_api_token == "0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345678"
    assert config.debug is True
    assert config.allowed_hosts == ["localhost"]


def test_pydantic_config_missing_token(tmp_path):
    test_config = textwrap.dedent(
        """
        TOSK_BOT_DEBUG=false
        TOSK_BOT_ALLOWED_HOSTS=["localhost"]
        """
    ).strip()
    # Create env file without telegram_api_token (required field)
    env_file = tmp_path / ".env"
    env_file.write_text(test_config)

    with pytest.raises(ValidationError):
        AppConfig(_env_file=str(env_file))


def test_pydantic_config_invalid_allowed_hosts(tmp_path):
    test_config = textwrap.dedent(
        """
        TOSK_BOT_TELEGRAM_API_TOKEN=token
        TOSK_BOT_ALLOWED_HOSTS=localhost
        """
    ).strip()
    # invalid allowed_hosts type (expect list)
    env_file = tmp_path / ".env"
    env_file.write_text(test_config)

    with pytest.raises(SettingsError):
        AppConfig(_env_file=str(env_file))
