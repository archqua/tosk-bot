import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import aio_pika as RMQ
import aiomisc
from aiormq import AMQPConnectionError, ChannelInvalidStateError
from pydantic import AnyUrl
from pydantic.json import pydantic_encoder
from teleapi import teleapi as TG

from .config import Settings, get_settings

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
    _consumer_tag: str | None = None

    async def connect(self, rabbitmq_url: AnyUrl):
        """
        Connect to RabbitMQ, declare exchange and queue, and bind queue with routing key.

        Args:
            rabbitmq_url: URL string to connect to RabbitMQ server.
        """
        self.connection = await RMQ.connect_robust(str(rabbitmq_url))
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

    async def disconnect(self) -> None:
        logger.info("Disconnecting from RabbitMQ")
        # if self.channel:
        #     await self.channel.close()
        if self.connection:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ")
        else:
            logger.info("Already disconnected from RabbitMQ")


@dataclass
class ServiceProxy:
    settings: Settings
    rmq: RabbitMQContext

    async def publish_pong(self, chat_id: int):
        """
        Publish a Telegram 'pong' message to RabbitMQ to respond to a /ping command.

        Args:
            chat_id: Telegram chat ID to send the pong message to.
        """
        method = "sendMessage"
        # TODO waiting for external implementation
        # payload = TG.sendMessagePayload(
        # TODO TG.Message(...).model_dump()?
        payload = dict(
            chat_id=chat_id,
            text="pong",
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
                )
            except Exception as e:
                logger.error(f"Failed to process ping message: {e}")

    @classmethod
    def from_service(cls, service: "Service") -> "ServiceProxy":
        return cls(service.settings, service.rmq)


class Service(aiomisc.service.ProcessService):
    """
    Ping service that listens for /ping commands on RabbitMQ and replies with 'pong' messages.

    Attributes:
        settings: Configuration settings loaded from environment or .env.
        rmq: Instance of RabbitMQContext managing RabbitMQ resources.
    """

    async def start(self) -> None:
        self.settings = get_settings()
        self.rmq = RabbitMQContext()
        await self.rmq.connect(self.settings.rabbitmq_url)
        self._runner = ServiceProxy.from_service(self)
        self.rmq._consumer_tag = await self.rmq.queue.consume(self._runner.pong)

    async def in_process(self) -> Any:
        await asyncio.Future()

    async def stop(self, exception: Exception = None) -> Any:
        # await self.rmq.queue.cancel(self.rmq._consumer_tag)
        await self.rmq.disconnect()


if __name__ == "__main__":
    with aiomisc.entrypoint(Service()) as loop:
        loop.run_forever()
