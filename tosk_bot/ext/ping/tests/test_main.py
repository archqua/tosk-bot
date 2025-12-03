import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from ext.ping.service import config
from ext.ping.service.main import Service
from pydantic.json import pydantic_encoder
from teleapi import teleapi as TG


@pytest.fixture(autouse=True)
def patch_get_settings(monkeypatch):
    monkeypatch.setenv("TOSK_BOT_BASE_RABBITMQ_URL", "amqp://guest:guest@localhost/")
    monkeypatch.setattr("ext.ping.service.main.get_settings", lambda: config.Settings())
    yield


@pytest.fixture
def service():
    return Service()


@pytest.mark.asyncio
async def test_publish_pong_calls_exchange_publish(service):
    # Setup exchange publish as AsyncMock
    service.rmq.exchange = MagicMock()
    service.rmq.exchange.publish = AsyncMock()

    chat_id = 123
    reply_id = 456
    await service.publish_pong(chat_id, reply_id)

    service.rmq.exchange.publish.assert_awaited_once()
    args, kwargs = service.rmq.exchange.publish.call_args
    message = args[0]
    routing_key = kwargs["routing_key"]

    assert routing_key == "base.output.sendMessage"
    body = json.loads(message.body.decode())
    assert body["chat_id"] == chat_id
    assert body["text"] == "pong"
    assert body["reply_to_message_id"] == reply_id


@pytest.mark.asyncio
async def test_pong_handles_incoming_message(service):
    # Prepare message payload (Telegram Message model dump)
    chat_id = 123
    message_id = 456
    payload = TG.Message(
        message_id=message_id,
        chat=TG.Chat(id=chat_id, type="private"),
        date=int(datetime.now(UTC).timestamp()),
        text="/ping",
    )
    body_bytes = json.dumps(payload.model_dump(), default=pydantic_encoder).encode()

    # Mock RMQ.IncomingMessage
    message = MagicMock()
    message.body = body_bytes

    @asynccontextmanager
    async def message_process(*args, **kwargs):
        yield

    message.process = message_process

    # Prepare publish_pong for spy
    service.publish_pong = AsyncMock()

    await service.pong(message)

    service.publish_pong.assert_awaited_once_with(
        chat_id=chat_id, reply_to_message_id=message_id
    )


@pytest.mark.asyncio
async def test_consume_queue_context_manager(service):
    async def dummy_callback(msg):
        pass

    service.rmq.queue = MagicMock()
    queue_mock = service.rmq.queue
    queue_mock.consume = AsyncMock(return_value="consumer_tag")
    queue_mock.cancel = AsyncMock()

    async with service.consume_queue(dummy_callback):
        queue_mock.consume.assert_awaited_once()
    queue_mock.cancel.assert_awaited_once_with("consumer_tag")


# TODO test run
