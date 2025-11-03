import pytest
from unittest.mock import MagicMock
from telegram import User, Chat, Update
from bot import handlers as H
import tests.mock as mock


@pytest.mark.asyncio
async def test_ping_handler():
    user = User(id=123, first_name="TestUser", is_bot=False)
    chat = Chat(id=456, type="private")
    msg = mock.message(text="/ping", chat=chat, from_user=user)

    update = MagicMock(spec=Update)
    update.message = msg

    ctx = mock.callback_context()

    await H.ping(update, ctx)
    msg.reply_text.assert_awaited_once_with("pong")


@pytest.mark.asyncio
async def test_start_handler():
    user = User(id=123, first_name="TestUser", is_bot=False)
    chat = Chat(id=456, type="private")
    msg = mock.message(text="/start", chat=chat, from_user=user)

    update = MagicMock(spec=Update)
    update.message = msg

    ctx = mock.callback_context()

    await H.start(update, ctx)
    msg.reply_text.assert_awaited()
    assert "welcome" in msg.reply_text.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_help_handler():
    user = User(id=123, first_name="TestUser", is_bot=False)
    chat = Chat(id=456, type="private")
    msg = mock.message(text="/help", chat=chat, from_user=user)

    update = MagicMock(spec=Update)
    update.message = msg

    ctx = mock.callback_context()

    await H.help(update, ctx)
    msg.reply_text.assert_awaited()
    text = msg.reply_text.call_args.args[0]
    assert "/start" in text and "/ping" in text and "/help" in text
