import asyncio
import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aio_pika
import pytest
import pytest_asyncio
from base.service.main import Service as BaseService
from ext.ping.service.main import Service as PingService
from teleapi import teleapi as TG
from testcontainers.rabbitmq import RabbitMqContainer

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def rmq_url():
    url = f"amqp://guest:guest@localhost:5672/"
    connection = await aio_pika.connect(url)
    yield url
    await connection.close()


@pytest_asyncio.fixture
async def settings_override(monkeypatch, rmq_url):
    monkeypatch.setenv("TOSK_BOT_BASE_TELEGRAM_API_TOKEN", "test_token")
    monkeypatch.setenv("TOSK_BOT_BASE_RABBITMQ_URL", rmq_url)
    yield


@pytest.mark.asyncio
async def test_ping_pong(settings_override):
    base_service = BaseService()
    ping_service = PingService()
    mock_teleapi_instance = MagicMock()
    first_call = True
    updates = [
        TG.Update(
            update_id=123,
            message=TG.Message(
                message_id=456,
                date=int(datetime.now(UTC).timestamp()),
                chat=TG.Chat(id=789, type="private"),
                text="/ping",
                entities=[
                    TG.MessageEntity(
                        type="bot_command",
                        offset=0,
                        length=len("/ping"),
                    )
                ],
            ),
        )
    ]

    async def mock_getUpdates(*args, **kwargs):
        nonlocal first_call
        if first_call:
            first_call = False
            return updates
        else:
            try:
                await asyncio.Future()
            finally:
                pass

    sent_data = []

    async def mock_sendMessage(data):
        nonlocal sent_data
        sent_data.append(data)
        return TG.Message(
            **data,
        )

    mock_teleapi_instance.getUpdates = AsyncMock(
        return_value=updates, side_effect=mock_getUpdates
    )
    mock_teleapi_instance.sendMessage = AsyncMock(side_effect=mock_sendMessage)
    patch_base = patch(
        "base.service.tgio.httpx_teleapi_factory_async",
        new=lambda *a, **k: mock_teleapi_instance,
    )
    with patch_base:
        base_task = asyncio.create_task(base_service.run())
        ping_task = asyncio.create_task(ping_service.run())
        await asyncio.sleep(0.2)
        assert sent_data[0]["text"] == "pong"
        base_task.cancel()
        ping_task.cancel()
