FROM python:3.11-slim-bookworm

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    UVICORN_WORKERS=2

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    find /usr/local -type d -name __pycache__ -prune -exec rm -rf '{}' + && \
    find /usr/local -type f -name '*.pyc' -delete && \
    rm -rf /root/.cache

RUN useradd -m -u 10001 appuser && \
    mkdir -p /data && \
    chown appuser:appuser /data

COPY apps/api /app
RUN chmod 755 /app/init_data.sh && \
    chown -R appuser:appuser /app

EXPOSE 8080
USER appuser

CMD ["/bin/sh", "-c", "sh /app/init_data.sh && gunicorn -k uvicorn.workers.UvicornWorker --workers $UVICORN_WORKERS --bind 0.0.0.0:$PORT app:app"]
