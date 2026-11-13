FROM python:3.15-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ROBO_TRAINER_HOME=/data

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install . \
    && useradd --create-home --uid 10001 trainer \
    && mkdir /data \
    && chown trainer /data

USER trainer
VOLUME /data
CMD ["robo-trainer-mcp"]
