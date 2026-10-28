FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WAREHOUSE=bigquery \
    PORT=8080

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install ".[bigquery]" \
    && useradd --create-home --uid 10001 app

USER app
EXPOSE 8080
# Cloud Run sets PORT; exec so uvicorn receives shutdown signals directly.
CMD ["sh", "-c", "exec uvicorn metrics_api.app:app --host 0.0.0.0 --port ${PORT}"]
