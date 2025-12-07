import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import aio_pika as RMQ
import aiomisc
from aiormq import AMQPConnectionError, ChannelInvalidStateError
from pydantic import AnyUrl
from pydantic.json import pydantic_encoder
from teleapi import teleapi as TG

from .config import Settings, get_settings
from .tgio import Input, Output, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RabbitMQContext:
    """
    Manages RabbitMQ connection, channel, exchange, and queue.

    Attributes:
        exchange_name: Name of the RabbitMQ exchange.
        connection: aio-pika connection instance.
        channel: aio-pika channel instance.
        exchange: Declared exchange.
        queue: Declared queue.
    """

    exchange_name: str = "tosk_bot_base_topic"
    connection: RMQ.Connection | None = None
    channel: RMQ.Channel | None = None
    exchange: RMQ.Exchange | None = None
    queue: RMQ.Queue | None = None

    async def connect(self, rabbitmq_url: AnyUrl) -> None:
        """
        Connect to RabbitMQ server, declare exchange and queue, and bind queue.

        Args:
            rabbitmq_url: URL of the RabbitMQ server.
        """
        self.connection = await RMQ.connect_robust(str(rabbitmq_url))
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            self.exchange_name, RMQ.ExchangeType.TOPIC, durable=True
        )
        self.queue = await self.channel.declare_queue(durable=True)
        await self.queue.bind(self.exchange, routing_key="base.output.*")
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

    @asynccontextmanager
    async def ctx(self, rabbitmq_url: AnyUrl) -> None:
        await self.connect(rabbitmq_url)
        try:
            yield
        finally:
            await self.disconnect()


@dataclass
class ServiceProxy:
    """A storage for service methods that are not part os aiomisc service interface"""

    settings: Settings | None = None
    rmq: RabbitMQContext | None = None
    input_instance: Input | None = None
    output_instance: Output | None = None

    @classmethod
    def from_service(cls, service: "Service") -> "ServiceProxy":
        return cls(
            settings=service.settings,
            rmq=service.rmq,
            input_instance=service.input_instance,
            output_instance=service.output_instance,
        )

    async def publish_user_text_message(self, user_message: TG.Message) -> None:
        """
        Publish a Telegram user text message to RabbitMQ.

        Args:
            user_message: Telegram message object containing text and metadata.

        Raises:
            Exceptions from RabbitMQ publishing are propagated after logging.
        """
        message_body = json.dumps(
            user_message.model_dump(), default=pydantic_encoder
        ).encode()
        message = RMQ.Message(body=message_body)
        routing_key = "base.input.message.text"
        if user_message.entities is not None and len(user_message.entities) > 0:
            first_entity = user_message.entities[0]
            begin = first_entity.offset
            end = begin + first_entity.length
            if first_entity.type == "bot_command":
                cmd, at, name = user_message.text[begin:end].partition("@")
                # TODO use getMe api call and check the bot name?
                cmd = cmd.lstrip("/")
                routing_key += f".cmd.{cmd}"
        await self.rmq.exchange.publish(message, routing_key=routing_key)
        user = user_message.from_
        if user is not None:
            sender = f"@{user.username} ({user.id})"
        else:
            sender = "<UNK>"
        logger.info(
            f"Published a {routing_key} message {user_message.message_id}"
            f" from user {sender} to RabbitMQ"
        )

    async def publish_api_response(self, response: Response):
        """
        Publish a Telegram API response message to RabbitMQ.

        Args:
            response: Response model containing method name and content.

        Raises:
            Exceptions from RabbitMQ publishing are propagated after logging.
        """
        message_body = json.dumps(response.contents, default=pydantic_encoder).encode()
        message = RMQ.Message(body=message_body)
        routing_key = f"base.response.{response.method}"
        await self.rmq.exchange.publish(message, routing_key=routing_key)
        logger.info(
            f"Published a {routing_key} message"
            f" with a response to a {response.method} call to RabbitMQ"
        )

    async def handle_telegram_update(self, update: TG.Update) -> None:
        """
        Async handler for Telegram updates.

        Parses and forwards user text messages to publish_user_text_message.
        Logs info for unhandled update types.

        Args:
            update: Incoming Telegram Update object.
        """
        # currently only user text messages
        if update.message is not None:
            if update.message.text is not None:
                try:
                    await self.publish_user_text_message(update.message)
                except Exception as e:
                    logger.error(f"Failed to publish user text message: {e}")
            else:
                logger.info("Unhandled non-text message update")
        else:
            present_fields = []
            for f, v in TG.Update.model_fields.items():
                if v is not None:
                    present_fields.append(f)
            gist = f"{update.update_id}::{'||'.join(present_fields)}"
            logger.info(f"Unhandled update: {gist}")

    async def handle_telegram_response(self, response: Response) -> None:
        """
        Async handler for Telegram API responses.

        Publishes the response and logs failures.

        Args:
            response: Response object to publish.
        """
        try:
            await self.publish_api_response(response)
        except Exception as e:
            logger.error(f"Failed to publish api response: {e}")

    async def tgio_input_handler(self, inp: TG.Update | Response) -> None:
        """
        Dispatch incoming input to correct handler based on type.

        Args:
            inp: Either Telegram Update or tgio Response.
        """
        if isinstance(inp, TG.Update):
            await self.handle_telegram_update(inp)
        elif isinstance(inp, Response):
            await self.handle_telegram_response(inp)
        else:
            logger.error(f"Failed to handle {type(inp)} input")

    async def handle_base_output_message(self, message: RMQ.IncomingMessage) -> None:
        """
        Process a RabbitMQ 'base.output.*' message and enqueue it for sending.

        Args:
            message: IncomingMessage object from aio-pika queue.

        Notes:
            Performs minimal validation and logs errors on malformed messages.
        """
        # TODO apply some RPC semantics
        logger.info("Handling Output message")
        async with message.process():
            try:
                payload = json.loads(message.body.decode())
                routing_key = message.routing_key.split(".")
                # TODO create a dev module with utils
                # expect base.output.{method}[.{tail}] format
                method = routing_key[2]
                # TODO come up with pydantic validation
                try:
                    logger.info(f"Requesting {method} call")
                    await asyncio.wait_for(
                        self.output_instance.request(method, payload),
                        timeout=1,
                    )
                except asyncio.TimeoutError:
                    # last resort is discarding updates
                    logger.error(
                        f"Output queue is full, discarding a {method} call request"
                    )
            except Exception as e:
                logger.error(f"Failed to process reply message: {e}")


# TODO exception handling
class Service(aiomisc.service.ProcessService):
    """
    Main service managing Telegram bot input/output integration with RabbitMQ.

    Attributes:
        settings: Application settings loaded from config.
        rmq: RabbitMQ context instance.
        input_instance: Instance of Input handler for Telegram updates.
        output_instance: Instance of Output handler for sending Telegram responses.
    """

    async def start(self) -> None:
        self.settings = get_settings()
        self.rmq = RabbitMQContext()
        await self.rmq.connect(self.settings.rabbitmq_url)

        # IO
        async def input_handler(update: TG.Update | Response) -> None:
            return await self.tgio_input_handler(update)

        self.input_instance = Input(
            token=self.settings.telegram_api_token,
            handler=input_handler,
        )
        self.output_instance = Output(
            token=self.settings.telegram_api_token,
            response_queue=self.input_instance.upd_queue,
        )
        # consumer
        self.rmq._consumer_tag = await self.rmq.queue.consume(self.pong)

    async def in_process(self) -> Any:
        """
        Main entry point to run the service.

        Connects to RabbitMQ, initializes input/output handlers, and
        starts consuming and processing messages asynchronously.

        This method runs indefinitely until cancelled or an exception occurs.
        """
        async with asyncio.TaskGroup() as task_group:
            tasks_created = asyncio.Event()
            task_group.create_task(
                self.output_instance.handle(notify_event=tasks_created),
            )
            await tasks_created.wait()
            tasks_created.clear()
            logger.info("Completed Output setup")
            task_group.create_task(
                self.input_instance.handle(notify_event=tasks_created),
            )
            await tasks_created.wait()
            tasks_created.clear()
            logger.info("Completed Input setup")

    async def stop(self, exception: Exception = None) -> Any:
        # await self.rmq.queue.cancel(self.rmq._consumer_tag)
        await self.rmq.disconnect()


if __name__ == "__main__":
    with aiomisc.entrypoint(Service()) as loop:
        loop.run_forever()
