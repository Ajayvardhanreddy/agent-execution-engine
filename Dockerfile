# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --frozen --no-dev

# Copy source
COPY . .

ENV PYTHONPATH=/app
EXPOSE 9000

CMD ["uv", "run", "uvicorn", "engine.api.app:app", "--host", "0.0.0.0", "--port", "9000"]
