FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WAREHOUSE=bigquery \
    PORT=8050

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install ".[bigquery]" \
    && useradd --create-home --uid 10001 app

USER app
EXPOSE 8050
# Cloud Run sets PORT; exec so gunicorn receives shutdown signals directly.
CMD ["sh", "-c", "exec gunicorn dashboard.app:server --bind 0.0.0.0:${PORT} --workers 2 --timeout 120"]
