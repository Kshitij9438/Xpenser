FROM python:3.11

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PRISMA_CACHE_DIR=/app/.prisma-cache

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    ca-certificates \
    openssl \
    libssl-dev \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN prisma generate

RUN chmod +x start.sh

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

RUN mkdir -p /app/.prisma-cache \
    && chown -R app:app /app/.prisma-cache

RUN find /usr/local/lib -path "*prisma*" -type d -exec chown -R app:app {} \; 2>/dev/null || true

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["bash", "./start.sh"]
