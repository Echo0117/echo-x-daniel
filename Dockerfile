# ---------- Runtime stage ----------
# syntax=docker/dockerfile:1.6

# ---------- Builder stage (cacheable deps) ----------
FROM python:3.11-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_BINARY=:none: \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /deps
# Only copy the lock/requirements to maximize cache hits
COPY requirements.txt ./
# Use BuildKit cache for pip; AI dependencies (torch, transformers) are commented out
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Runtime stage ----------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    UVICORN_WORKERS=2

# Only runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser

WORKDIR /app
# Bring in site-packages from builder without dev toolchain
COPY --from=builder /install /usr/local

# Copy app code last to leverage cached deps layer
COPY apps ./apps

EXPOSE 8080
USER appuser

# Keep shell form to allow env var expansion for PORT/WORKERS
CMD gunicorn \
  -k uvicorn.workers.UvicornWorker \
  --workers ${UVICORN_WORKERS} \
  --bind 0.0.0.0:${PORT} \
  app:app \
  --chdir apps/api
