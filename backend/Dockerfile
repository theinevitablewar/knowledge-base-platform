# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS runtime

ARG PYPI_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=0 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/root/.cache/uv \
    UV_CONCURRENT_DOWNLOADS=10 \
    PIP_INDEX_URL=${PYPI_INDEX_URL} \
    UV_DEFAULT_INDEX=${PYPI_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=120 \
    UV_HTTP_TIMEOUT=120 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,id=knowledge-base-uv-cache,target=/root/.cache/uv,sharing=locked \
    uv sync \
      --frozen \
      --no-dev \
      --no-install-project

COPY . .

RUN --mount=type=cache,id=knowledge-base-uv-cache,target=/root/.cache/uv,sharing=locked \
    uv sync \
      --frozen \
      --no-dev

EXPOSE 8000

CMD ["sh", "-c", "/app/.venv/bin/alembic upgrade head && /app/.venv/bin/python -m app.scripts.seed && exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"]