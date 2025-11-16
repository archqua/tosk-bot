import os
import pytest
import textwrap
from pydantic import ValidationError
from base.service.config import Settings, get_settings


def test_env_variables(monkeypatch):
    monkeypatch.setenv("TOSK_BOT_BASE_TELEGRAM_API_TOKEN", "env_token")
    monkeypatch.setenv(
        "TOSK_BOT_BASE_RABBITMQ_URL", "amqp://env_user:env_pass@localhost/"
    )

    settings = Settings()
    assert settings.telegram_api_token == "env_token"
    assert str(settings.rabbitmq_url).startswith("amqp://env_user:env_pass@localhost")


def test_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        textwrap.dedent(
            """
        TOSK_BOT_BASE_TELEGRAM_API_TOKEN=envfile_token
        TOSK_BOT_BASE_RABBITMQ_URL=amqp://file_user:file_pass@localhost/
        """
        ).strip()
    )

    settings = Settings(_env_file=str(env_file))
    assert settings.telegram_api_token == "envfile_token"
    assert str(settings.rabbitmq_url).startswith("amqp://file_user:file_pass@localhost")
