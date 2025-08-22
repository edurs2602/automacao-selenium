FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir -U pip uv \
    && uv sync

COPY . .

RUN mkdir -p /app/data

CMD ["uv", "run", "python", "-m", "app.services.doc_scraper"]
