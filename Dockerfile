FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

CMD ["robo-trainer-mcp"]
