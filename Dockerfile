FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install poetry \
 && poetry config virtualenvs.create false \
 && poetry install --without dev --no-interaction --no-ansi

COPY bot ./bot

CMD ["python", "-m", "bot.main"]
