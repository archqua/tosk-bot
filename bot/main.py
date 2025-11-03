from bot.handlers import handler_registry
from telegram.ext import ApplicationBuilder, CommandHandler
from bot.config import settings


def main():
    app = ApplicationBuilder().token(settings.api_token).build()

    for cmd_name, func in handler_registry:
        app.add_handler(CommandHandler(cmd_name, func))

    app.run_polling()
