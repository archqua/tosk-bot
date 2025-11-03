from telegram import Update
from telegram.ext import ContextTypes

handler_registry = []


def handler(func):
    """
    Decorator to register a command handler.
    Uses the function name as the command name.
    """
    cmd_name = func.__name__
    handler_registry.append((cmd_name, func))
    return func


@handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with bot info"""
    await update.message.reply_text(
        "Hello! 👋 Welcome to the bot.\n" "Use /help to see available commands."
    )


@handler
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responds with 'pong' to check server health"""
    await update.message.reply_text("pong")


@handler
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Auto-generates help text by listing all registered commands and their docstrings.
    """
    help_lines = ["Available commands:\n"]
    # Retrieve commands and their docstrings from registered handlers
    for cmd, func in sorted(handler_registry):
        desc = func.__doc__ or "No description."
        help_lines.append(f"/{cmd} - {desc.strip()}")
    help_text = "\n".join(help_lines)
    await update.message.reply_text(help_text)
