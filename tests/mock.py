from unittest.mock import AsyncMock, MagicMock
from telegram import Message
from telegram.ext import CallbackContext


def message(text="/start", chat=None, from_user=None):
    """
    Creates a MagicMock spec'd as telegram.Message and sets attributes.
    reply_text is an AsyncMock to simulate async method.
    """
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.chat = chat
    msg.from_user = from_user
    msg.reply_text = AsyncMock()
    return msg


def callback_context():
    """
    Creates a MagicMock spec'd as telegram.ext.CallbackContext with a mocked bot property.
    """
    ctx = MagicMock(spec=CallbackContext)
    type(ctx).bot = MagicMock()
    return ctx
