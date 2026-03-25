# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS builder
ARG INSTALL_HF=0
WORKDIR /opt/app
# copy only requirements to maximize cache hits
COPY requirements.txt requirements.txt
COPY requirements-hf.txt requirements-hf.txt
RUN pip install --upgrade pip && \
	pip install --no-cache-dir --no-compile --prefix=/install -r requirements.txt && \
	if [ "$INSTALL_HF" = "1" ]; then \
		pip install --no-cache-dir --no-compile --prefix=/install --index-url https://download.pytorch.org/whl/cpu "torch==2.4.*" && \
		pip install --no-cache-dir --no-compile --prefix=/install -r requirements-hf.txt; \
	fi && \
	find /install -type d -name __pycache__ -prune -exec rm -rf '{}' + && \
	find /install -type f -name '*.pyc' -delete

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/* && useradd -m appuser && mkdir -p /data && chown appuser:appuser /data
WORKDIR /app
COPY --from=builder /install /usr/local
COPY apps/api /app
RUN chown -R appuser:appuser /app
ENV PORT=8080
EXPOSE 8080
USER appuser
CMD sh -c "sh /app/init_data.sh && python -m uvicorn app:app --host 0.0.0.0 --port ${PORT}"
