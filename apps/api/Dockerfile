# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/app
# copy only requirements to maximize cache hits
COPY apps/api/requirements.txt requirements.txt
# use BuildKit cache for pip; install CPU-only PyTorch first to avoid large CUDA wheels
RUN --mount=type=cache,id=pip-cache-api,target=/root/.cache/pip \
	pip install --upgrade pip && \
	pip install --no-cache-dir --prefix=/install --index-url https://download.pytorch.org/whl/cpu "torch==2.4.*" && \
	pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
RUN useradd -m appuser && mkdir -p /data && chown appuser:appuser /data
WORKDIR /app
COPY --from=builder /install /usr/local
COPY apps/api /app
RUN mkdir -p /app/letters /app/poems/mine /app/poems/found /app/static && chown -R appuser:appuser /app
ENV PORT=8080
EXPOSE 8080
USER appuser
CMD sh -c "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT}"
