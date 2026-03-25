# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS builder
ARG INSTALL_HF=0
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /deps
# Only copy the lock/requirements to maximize cache hits
COPY requirements.txt requirements.txt
COPY requirements-hf.txt requirements-hf.txt
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir --no-compile --prefix=/install -r requirements.txt && \
    if [ "$INSTALL_HF" = "1" ]; then \
      pip install --no-cache-dir --no-compile --prefix=/install --index-url https://download.pytorch.org/whl/cpu "torch==2.4.*" && \
      pip install --no-cache-dir --no-compile --prefix=/install -r requirements-hf.txt; \
    fi && \
    find /install -type d -name __pycache__ -prune -exec rm -rf '{}' + && \
    find /install -type f -name '*.pyc' -delete

# ---------- Runtime stage ----------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    UVICORN_WORKERS=2

# Only runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

WORKDIR /app
# Bring in site-packages from builder without dev toolchain
COPY --from=builder /install /usr/local

# Copy only the API app into the runtime image
COPY apps/api /app

# Make init script executable and readable by appuser
RUN chmod 755 /app/init_data.sh && \
    chown -R appuser:appuser /app

EXPOSE 8080
USER appuser

# Keep shell form to allow env var expansion for PORT/WORKERS
# First initialize data, then start gunicorn
CMD sh /app/init_data.sh && gunicorn -k uvicorn.workers.UvicornWorker --workers ${UVICORN_WORKERS} --bind 0.0.0.0:${PORT} app:app
