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

# Pre-generate schema (this will be regenerated in start.sh with actual DATABASE_URL)
RUN prisma generate || true

RUN chmod +x start.sh

# Create user BEFORE setting permissions
RUN useradd --create-home --shell /bin/bash app

# Create and set permissions for Prisma cache
RUN mkdir -p /app/.prisma-cache && \
    chmod 755 /app/.prisma-cache

# 🔥 CRITICAL: Give ownership to app user for all necessary directories
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Ensure Prisma binaries are executable
RUN find ~/.cache -name "prisma-*" -type f -exec chmod +x {} \; 2>/dev/null || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["bash", "./start.sh"]