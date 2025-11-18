import asyncio

import aio_pika
import pytest
from base.service import main
from testcontainers.rabbitmq import RabbitMqContainer


@pytest.fixture(scope="session")
def event_loop():
    # Provide a session-scoped event loop for asyncio tests
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def rabbitmq_container():
    # Spin up a RabbitMQ container for the full test session
    with RabbitMqContainer("rabbitmq:4.2-management") as rabbitmq:
        yield rabbitmq.get_connection_url()


@pytest.fixture
async def rmq_connection(rabbitmq_container):
    # Aio-pika connection to the running RabbitMQ container
    connection = await aio_pika.connect_robust(rabbitmq_container)
    yield connection
    await connection.close()


@pytest.fixture
def settings_override(monkeypatch, rabbitmq_container):
    # Override environment variables to satisfy your Settings model
    monkeypatch.setenv("TOSK_BOT_BASE_TELEGRAM_API_TOKEN", "test_token")
    monkeypatch.setenv("TOSK_BOT_BASE_RABBITMQ_URL", rabbitmq_container)
    yield


@pytest.fixture
async def service_with_rmq(settings_override, rmq_connection):
    # Initialize and connect your service under test to RabbitMQ
    svc = main.Service()
    await svc.connect_rabbitmq()
    yield svc
    await svc.rmq.connection.close()
