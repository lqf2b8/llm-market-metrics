FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MEMO_DIR=/memos

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install . \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /memos && chown app /memos

USER app
ENTRYPOINT ["python", "-m", "memo.draft"]
