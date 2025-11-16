FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml poetry.lock /app/

RUN pip install --no-cache-dir poetry

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --without dev

COPY tosk_bot/base/service ./tosk_bot/base/service

# Disable stdout/stderr buffering for better logging
ENV PYTHONUNBUFFERED=1
# No .pyc and __pycache__ to keep the container lightweight
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "tosk_bot.base.service.main"]
