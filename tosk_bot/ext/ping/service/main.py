import asyncio
import json
import logging

from aio_pika import connect_robust, ExchangeType, IncomingMessage, Message
from pydantic.json import pydantic_encoder
from telegram.ext import ApplicationBuilder, MessageHandler, filters

from .config import get_settings
from .models import UserMessage, BotReply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Service:
    def __init__(self):
        self.settings = get_settings()
        self.exchange_name = (
            "tosk_bot_incomming_messages"  # Same exchange as base service
        )
        self.connection = None
        self.channel = None
        self.exchange = None
        self.queue = None
        self.app = None

    async def connect_rabbitmq(self):
        self.connection = await connect_robust(self.settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            self.exchange_name, ExchangeType.FANOUT
        )
        # Declare a queue with a unique name for this service and bind to exchange
        self.queue = await self.channel.declare_queue(exclusive=True)
        await self.queue.bind(self.exchange)
        logger.info("Connected to RabbitMQ and bound queue")

    async def handle_ping_message(self, message: IncomingMessage):
        async with message.process():
            try:
                payload = message.body.decode()
                user_msg = UserMessage.model_validate_json(payload)
                # Only respond if the message text is "/ping"
                if user_msg.text.strip().lower() == "/ping":
                    reply = BotReply(
                        chat_id=user_msg.chat_id,
                        reply_to_message_id=user_msg.message_id,
                        text="pong",
                    )
                    # Publish BotReply as JSON message to exchange
                    body = json.dumps(
                        reply.model_dump(), default=pydantic_encoder
                    ).encode()
                    await self.exchange.publish(Message(body=body), routing_key="")
                    logger.info(f"Responded with pong to chat_id={reply.chat_id}")
            except Exception as e:
                logger.error(f"Failed to process ping message: {e}")

    async def run(self):
        await self.connect_rabbitmq()

        self.app = ApplicationBuilder().token(None).build()  # No Telegram commands here
        # Consume messages from queue to handle /ping commands (from base service)
        consumer_task = asyncio.create_task(
            self.queue.consume(self.handle_ping_message)
        )

        # No Telegram bot polling needed as this extension handles messages from RabbitMQ

        logger.info("Ping service started. Waiting for /ping messages.")
        await consumer_task  # Run forever


if __name__ == "__main__":
    service = Service()
    asyncio.run(service.run())
