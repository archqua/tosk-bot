import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock
from base.service import tgio
from teleapi.teleapi import Update


@pytest.mark.asyncio
async def test_tokenhash_returns_expected_length_and_chars():
    token = "super_secret_token"
    result = tgio.tokenhash(token)
    assert isinstance(result, str)
    assert len(result) in [43, 44]  # typical urlsafe base64 length for SHA-256
    assert all(c.isalnum() or c in ["-", "_", "="] for c in result)


@pytest.mark.asyncio
async def test_input_worker_processes_updates_and_handles_cancel():
    processed_queue = asyncio.Queue(maxsize=1)

    async def handler(update):
        await processed_queue.put(update)

    input_handler = tgio.Input(token="dummy", handler=handler, workers=1, queue_size=10)
    update = MagicMock(spec=Update)
    await input_handler.upd_queue.put(update)

    worker_task = asyncio.create_task(input_handler.worker())

    processed = [await asyncio.wait_for(processed_queue.get(), timeout=0.1)]
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    assert processed == [update]


@pytest.mark.asyncio
async def test_input_handle_fetches_updates_and_puts_in_queue(monkeypatch):
    updates = [MagicMock(spec=Update, update_id=i) for i in range(3)]

    async def mock_getUpdates(offset, timeout, limit):
        # will return [0, 1], [2], []...
        if offset > 2:
            await asyncio.sleep(timeout)
            return []
        return updates[offset : offset + 2]

    input_handler = tgio.Input(
        token="dummy", handler=AsyncMock(), workers=1, queue_size=3
    )
    monkeypatch.setattr(input_handler.teleapi, "getUpdates", mock_getUpdates)

    async with asyncio.TaskGroup() as tg:
        task = tg.create_task(input_handler.handle())
        queued = await asyncio.wait_for(
            asyncio.gather(
                *[input_handler.upd_queue.get() for _ in range(len(updates))]
            ),
            timeout=0.1,
        )
        task.cancel()

    assert input_handler.upd_queue.empty()
    assert all(isinstance(u, MagicMock) for u in queued)


@pytest.mark.asyncio
async def test_output_worker_calls_teleapi_methods_and_handles_cancel(monkeypatch):
    teleapi_mock = AsyncMock()
    called_payloads = []

    async def mock_method(payload):
        called_payloads.append(payload)

    teleapi_mock.sendMessage = mock_method

    output_handler = tgio.Output(token="dummy", workers=1, queue_size=5)
    monkeypatch.setattr(output_handler, "teleapi", teleapi_mock)

    await output_handler.upd_queue.put(("sendMessage", {"text": "hello"}))

    worker_task = asyncio.create_task(output_handler.worker())

    try:
        await asyncio.wait_for(output_handler.upd_queue.join(), timeout=0.1)
    except asyncio.TimeoutError:
        pass

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    assert called_payloads == [{"text": "hello"}]


@pytest.mark.asyncio
async def test_queue_put_timeout_on_input_handle(monkeypatch, caplog):
    updates = [MagicMock(spec=Update, update_id=i) for i in range(3)]

    async def mock_getUpdates(offset, timeout, limit):
        # will return [0, 1], [2], []...
        if offset > 2:
            await asyncio.sleep(timeout)
            return []
        return updates[offset : offset + 2]

    input_handler = tgio.Input(
        token="dummy", handler=AsyncMock(), workers=1, queue_size=1
    )
    monkeypatch.setattr(input_handler.teleapi, "getUpdates", mock_getUpdates)

    await input_handler.upd_queue.put(MagicMock(update_id=1))

    # Patch handler to block indefinitely, keeping queue full
    async def hang(*args, **kwargs):
        await asyncio.sleep(100)  # pytest timeout is 5 seconds anyway

    input_handler.handler = hang

    async def limited_handle():
        async with asyncio.TaskGroup() as task_group:
            task = task_group.create_task(input_handler.handle())
            await asyncio.sleep(1.1)
            task.cancel()

    await limited_handle()
    assert any(
        "Input queue is full, discarding incoming update" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_output_handle_accepts_external_updates(monkeypatch):
    teleapi_mock = AsyncMock()
    called_payloads = []

    async def mock_method(payload):
        called_payloads.append(payload)

    teleapi_mock.sendMessage = mock_method
    output_handler = tgio.Output(token="dummy", workers=1, queue_size=5)
    monkeypatch.setattr(output_handler, "teleapi", teleapi_mock)

    # Put an update externally into the queue before starting handle()
    await output_handler.upd_queue.put(("sendMessage", {"text": "test"}))

    async def limited_handle():
        async with asyncio.TaskGroup() as tg:
            task = tg.create_task(output_handler.handle())
            # Wait shortly to allow worker to consume
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    await limited_handle()

    # Confirm worker processed the externally enqueued update
    assert called_payloads == [{"text": "test"}]
