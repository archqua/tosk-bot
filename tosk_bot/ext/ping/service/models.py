from pydantic import BaseModel, Field
from typing import Optional


class UserMessage(BaseModel):
    """
    Model representing an incoming user message.
    """
    user_id: int = Field(..., description="Unique identifier of the user")
    username: Optional[str] = Field(None, description="Username of the user")
    chat_id: int = Field(..., description="Chat identifier where message was sent")
    message_id: int = Field(..., description="Unique identifier of the message")
    text: str = Field(..., description="Text content of the user message")


class BotReply(BaseModel):
    """
    Model for replies sent by the bot.
    """
    chat_id: int = Field(..., description="Chat identifier to send the reply to")
    reply_to_message_id: int = Field(..., description="Original message ID the reply refers to")
    text: str = Field(..., description="Text content of the reply message")
