import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from base.service import config, main, tgio
from teleapi import teleapi as TG


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
    monkeypatch.setattr(
        mock_channel, "declare_exchange", AsyncMock(return_value=mock_exchange)
    )
    monkeypatch.setattr(
        mock_channel, "declare_queue", AsyncMock(return_value=mock_queue)
    )
    monkeypatch.setattr(mock_queue, "bind", AsyncMock())
    ctx.settings = MagicMock(rabbitmq_url="amqp://test")
    await ctx.connect("amqp://test")
    mock_conn.channel.assert_awaited_once()
    mock_channel.declare_exchange.assert_awaited_once_with(
        ctx.exchange_name, main.RMQ.ExchangeType.TOPIC, durable=True
    )
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
async def test_tgio_input_handler_update_calls_publish(monkeypatch):
    service = main.Service()
    monkeypatch.setattr(service, "publish_user_text_message", AsyncMock())
    update = MagicMock(spec=TG.Update)
    update.message = MagicMock()
    update.message.text = "hello"
    await service.tgio_input_handler(update)
    service.publish_user_text_message.assert_awaited_once_with(update.message)


@pytest.mark.asyncio
async def test_tgio_input_handler_update_unhandled(monkeypatch, caplog):
    service = main.Service()
    update = MagicMock(spec=TG.Update)
    update.message = None
    update.update_id = 99
    with caplog.at_level("INFO"):
        await service.tgio_input_handler(update)
    assert "Unhandled update" in "".join(r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handle_base_output_message(monkeypatch):
    service = main.Service()
    service.output_instance = MagicMock()
    service.output_instance.request = AsyncMock()
    message = MagicMock()
    message.body = b'{"text": "hi"}'
    message.routing_key = "base.output.sendMessage"

    @asynccontextmanager
    async def message_process(*args, **kwargs):
        yield

    message.process = message_process
    await service.handle_base_output_message(message)
    (
        service.output_instance.request.assert_awaited_once_with(
            "sendMessage", {"text": "hi"}
        )
    )


@pytest.mark.asyncio
async def test_run_starts_handlers_and_consumes(monkeypatch):
    service = main.Service()

    service.connect_rabbitmq = AsyncMock()
    mock_queue = AsyncMock()
    service.rmq = AsyncMock()
    service.rmq.queue = mock_queue

    async def mock_consume(callback):
        await callback()

    mock_queue.consume = AsyncMock(
        return_value="consumer_tag", side_effect=mock_consume
    )
    mock_queue.cancel = AsyncMock()

    # Create a mock teleapi client with async getUpdates method
    mock_teleapi_instance = MagicMock()
    first_call = True

    async def mock_getUpdates(*args, **kwargs):
        nonlocal first_call
        if first_call:
            first_call = False
            update_mock = MagicMock(spec=TG.Update)
            update_mock.update_id = 123
            return [update_mock]
        else:
            await asyncio.Future()

    mock_teleapi_instance.getUpdates = AsyncMock(side_effect=mock_getUpdates)

    # Patch the factory to return the mocked teleapi client
    with patch(
        "base.service.tgio.httpx_teleapi_factory_async",
        new=lambda *args, **kwargs: mock_teleapi_instance,
    ):

        monkeypatch.setattr(service, "tgio_input_handler", AsyncMock())
        monkeypatch.setattr(service, "handle_base_output_message", AsyncMock())

        # Run service.run with a timeout to prevent indefinite hanging
        await asyncio.wait_for(service.run(), timeout=0.2)

    mock_queue.consume.assert_awaited_once()
    mock_queue.cancel.assert_awaited_once()
    service.tgio_input_handler.assert_awaited_once()
    service.handle_base_output_message.assert_awaited_once()
