import asyncio
from contextlib import asynccontextmanager
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from base.service import config, main, tgio
from teleapi.teleapi import Update


@pytest.fixture(autouse=True)
def patch_get_settings(monkeypatch):
    settings = config.Settings(
        telegram_api_token="test_token",
        rabbitmq_url="amqp://guest:guest@localhost/",
    )
    monkeypatch.setattr("base.service.main.get_settings", lambda: settings)
    yield


@pytest.mark.asyncio
async def test_rabbitmq_context_connect(monkeypatch):
    ctx = main.RabbitMQContext()
    mock_conn = AsyncMock()
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_queue = AsyncMock()
    monkeypatch.setattr(main.RMQ, "connect_robust", AsyncMock(return_value=mock_conn))
    mock_conn.channel = AsyncMock(return_value=mock_channel)
    monkeypatch.setattr(mock_channel, "declare_exchange", AsyncMock(return_value=mock_exchange))
    monkeypatch.setattr(mock_channel, "declare_queue", AsyncMock(return_value=mock_queue))
    monkeypatch.setattr(mock_queue, "bind", AsyncMock())
    ctx.settings = MagicMock(rabbitmq_url="amqp://test")
    await ctx.connect("amqp://test")
    mock_conn.channel.assert_awaited_once()
    mock_channel.declare_exchange.assert_awaited_once_with(ctx.exchange_name, main.RMQ.ExchangeType.TOPIC, durable=True)
    mock_channel.declare_queue.assert_awaited_once_with(durable=True)
    mock_queue.bind.assert_awaited_once_with(mock_exchange, routing_key="base.output")

@pytest.mark.asyncio
async def test_publish_user_text_message(monkeypatch):
    service = main.Service()
    service.rmq = MagicMock()
    service.rmq.exchange = AsyncMock()
    user_message = MagicMock()
    user_message.model_dump = MagicMock(return_value={"text": "hi"})
    user_message.entities = []
    user_message.message_id = 123
    user_message.from_ = MagicMock(username="tester", id=42)
    await service.publish_user_text_message(user_message)
    service.rmq.exchange.publish.assert_awaited_once()
    # Test behavior with a bot command entity
    entity = MagicMock()
    entity.type = "bot_command"
    entity.partition = MagicMock(return_value=("/start", "@", "botname"))
    user_message.entities = [entity]
    await service.publish_user_text_message(user_message)
    assert service.rmq.exchange.publish.await_count == 2

@pytest.mark.asyncio
async def test_publish_api_response(monkeypatch):
    service = main.Service()
    service.rmq = MagicMock()
    service.rmq.exchange = AsyncMock()
    response = tgio.Response(method="sendMessage", contents={"ok": True})
    await service.publish_api_response(response)
    service.rmq.exchange.publish.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_telegram_update_calls_publish(monkeypatch):
    service = main.Service()
    monkeypatch.setattr(service, "publish_user_text_message", AsyncMock())
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = "hello"
    await service.handle_telegram_update(update)
    service.publish_user_text_message.assert_awaited_once_with(update.message)

@pytest.mark.asyncio
async def test_handle_telegram_update_unhandled(monkeypatch, caplog):
    service = main.Service()
    update = MagicMock()
    update.message = None
    update.update_id = 99
    with caplog.at_level("INFO"):
        await service.handle_telegram_update(update)
    assert "Unhandled update" in "".join(r.message for r in caplog.records)

@pytest.mark.asyncio
async def test_handle_base_output_message(monkeypatch):
    service = main.Service()
    service.output_instance = MagicMock()
    service.output_instance.upd_queue = AsyncMock()
    message = MagicMock()
    message.body = b'{"method": "sendMessage", "payload": {"text": "hi"}}'
    @asynccontextmanager
    async def message_process(*args, **kwargs):
        yield
    message.process = message_process
    await service.handle_base_output_message(message)
    (
        service.output_instance.upd_queue.put
        .assert_awaited_once_with(("sendMessage", {"text": "hi"}))
    )

@pytest.mark.asyncio
async def test_run_starts_handlers_and_consumes(monkeypatch):
    service = main.Service()
    service.connect_rabbitmq = AsyncMock()
    monkeypatch.setattr(service, "tgio_input_handler", AsyncMock())
    monkeypatch.setattr(service, "handle_base_output_message", AsyncMock())

    # Patch Input, Output instantiation
    async def fake_handle(*args, notify_event=None, **kwargs) -> None:
        notify_event.set()
    input_mock, output_mock = MagicMock(), MagicMock()
    input_mock.handle = AsyncMock(side_effect=fake_handle)
    output_mock.handle = AsyncMock(side_effect=fake_handle)
    monkeypatch.setattr(main, "Input", lambda **kwargs: input_mock)
    monkeypatch.setattr(main, "Output", lambda **kwargs: output_mock)

    # Patch RabbitMQ queue.consume
    mock_queue = AsyncMock()
    service.rmq.queue = mock_queue
    mock_queue.consume = AsyncMock(return_value="consumer_tag")
    mock_queue.cancel = AsyncMock()

    await service.run()

    mock_queue.consume.assert_awaited_once()
    mock_queue.cancel.assert_awaited_once()
    input_mock.handle.assert_awaited_once()
    output_mock.handle.assert_awaited_once()
