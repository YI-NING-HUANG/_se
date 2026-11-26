FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY xfrescue ./xfrescue
COPY pyproject.toml README.md ./

WORKDIR /data
VOLUME ["/data"]

ENTRYPOINT ["python", "-m", "xfrescue"]
