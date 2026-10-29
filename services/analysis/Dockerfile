FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WAREHOUSE=bigquery

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install ".[bigquery]" \
    && useradd --create-home --uid 10001 app

USER app
CMD ["python", "-m", "analysis"]
