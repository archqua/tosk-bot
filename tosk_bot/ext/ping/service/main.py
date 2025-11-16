import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import logging
from typing import Callable, Awaitable

import aio_pika as RMQ
from pydantic import AnyUrl
from pydantic.json import pydantic_encoder
from teleapi import teleapi as TG

from .config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RabbitMQContext:
    """
    Manages connection and setup for RabbitMQ entities used by the service.

    Attributes:
        exchange_name: Name of the exchange to publish/consume messages.
        connection: The aio-pika connection instance.
        channel: The channel within the connection.
        exchange: The declared exchange instance.
        queue: The declared queue instance.
    """

    exchange_name: str = "tosk_bot_base_topic"
    connection: RMQ.Connection | None = None
    channel: RMQ.Channel | None = None
    exchange: RMQ.Exchange | None = None
    queue: RMQ.Queue | None = None

    async def connect(self, rabbitmq_url: AnyUrl):
        """
        Connect to RabbitMQ, declare exchange and queue, and bind queue with routing key.

        Args:
            rabbitmq_url: URL string to connect to RabbitMQ server.
        """
        self.connection = await RMQ.connect_robust(rabbitmq_url)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            self.exchange_name, RMQ.ExchangeType.TOPIC, durable=True
        )
        self.queue = await self.channel.declare_queue(durable=True)
        await self.queue.bind(
            self.exchange,
            routing_key="base.input.message.text.cmd.ping",
        )
        logger.info("Connected to RabbitMQ")


class Service:
    """
    Ping service that listens for /ping commands on RabbitMQ and replies with 'pong' messages.

    Attributes:
        settings: Configuration settings loaded from environment or .env.
        rmq: Instance of RabbitMQContext managing RabbitMQ resources.
    """

    def __init__(self):
        """Initialize service with settings and RabbitMQ context."""
        self.settings = get_settings()
        self.rmq = RabbitMQContext()

    async def connect_rabbitmq(self):
        """
        Connect to RabbitMQ server via RabbitMQContext.
        """
        await self.rmq.connect(rabbitmq_url=self.settings.rabbitmq_url)

    async def publish_pong(self, chat_id: int, reply_to_message_id: int | None = None):
        """
        Publish a Telegram 'pong' message to RabbitMQ to respond to a /ping command.

        Args:
            chat_id: Telegram chat ID to send the pong message to.
            reply_to_message_id: Message ID to reply to, enables Telegram threaded response.
        """
        method = "sendMessage"
        # TODO waiting for external implementation
        # payload = TG.sendMessagePayload(
        payload = dict(
            chat_id=chat_id,
            text="pong",
            reply_to_message_id=reply_to_message_id,
        )
        # TODO waiting for external implementation
        # message_body = json.dumps(payload.model_dump(), default=pydantic_encoder).encode()
        message_body = json.dumps(payload, default=pydantic_encoder).encode()
        message = RMQ.Message(body=message_body)
        routing_key = f"base.output.{method}"
        # called from `pong` method, exceptions are handled there
        await self.rmq.exchange.publish(message, routing_key=routing_key)
        logger.info(f"Published pong message to chat {chat_id}")

    async def pong(self, message: RMQ.IncomingMessage) -> None:
        """
        Callback invoked on incoming RabbitMQ messages.

        Parses incoming Telegram message payload, validates it, then sends pong response.

        Args:
            message: Incoming RabbitMQ message object.
        """
        async with message.process():
            try:
                payload = json.loads(message.body.decode())
                tg_message = TG.Message.model_validate(payload)
                await self.publish_pong(
                    chat_id=tg_message.chat.id,
                    reply_to_message_id=tg_message.message_id,
                )
                logger.info("Processed ping message and responded with pong")
            except Exception as e:
                logger.error(f"Failed to process ping message: {e}")

    @asynccontextmanager
    async def consume_queue(
        self,
        callback: Callable[[RMQ.IncomingMessage], Awaitable[None]],
    ):
        """
        Async context manager that starts consuming a RabbitMQ queue and ensures graceful cleanup.

        Args:
            callback: Async callable to process each incoming message.

        Yields:
            None: Control is yielded to allow awaiting within context.
        """
        consumer_tag = await self.rmq.queue.consume(callback)
        try:
            yield
        finally:
            await self.rmq.queue.cancel(consumer_tag)

    async def run(self) -> None:
        """
        Main service entry point to connect and start consuming messages indefinitely.

        Sets up RabbitMQ connection and queue consumption using `consume_queue` context manager.
        """
        try:

            async def run(self) -> None:
                await self.connect_rabbitmq()

                async with self.consume_queue(self.pong):
                    await asyncio.Future()

        except asyncio.CancelledError:
            logger.info("Ping extension service canceled")


if __name__ == "__main__":
    service = Service()
    asyncio.run(service.run())
