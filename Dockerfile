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

# TODO Phase 6: set PYTHONPATH and entrypoint once API module is built
ENV PYTHONPATH=/app
EXPOSE 9000

# Placeholder — replace with: uv run uvicorn api.main:app --host 0.0.0.0 --port 9000
CMD ["uv", "run", "python", "-c", "print('Agent Execution Engine — not yet configured')"]
