FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DBT_PROFILES_DIR=/app \
    DBT_TARGET=bigquery

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /warehouse && chown app /warehouse

COPY --chown=app . .
# dbt writes logs/, target/ and .user.yml next to the project: the app user must own /app.
RUN chown app /app
USER app

ENTRYPOINT ["dbt"]
# First pass. The forecast models read the analysis service's output, so they build in a
# second pass after it runs: `dbt build --select tag:post_analysis`.
CMD ["build", "--exclude", "tag:post_analysis"]
