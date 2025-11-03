import asyncio
import logging
from bot.handlers import handler_registry
from telegram.ext import ApplicationBuilder, CommandHandler
from bot.config import settings
import pydantic


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    try:
        app = ApplicationBuilder().token(settings.telegram_api_token).build()
        for cmd_name, func in handler_registry:
            app.add_handler(CommandHandler(cmd_name, func))

        app.run_polling()
        return 0  # Success exit code
    except pydantic.ValidationError as e:
        logger.error(f"Pydantic Validation Error(s) encountered:\n{e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
