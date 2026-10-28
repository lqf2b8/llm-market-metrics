FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DBT_PROFILES_DIR=/app \
    DBT_TARGET=bigquery

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && useradd --create-home --uid 10001 app

COPY --chown=app . .
USER app

ENTRYPOINT ["dbt"]
CMD ["build"]
