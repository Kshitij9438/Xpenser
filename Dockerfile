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

# Generate Prisma as ROOT (before switching users)
RUN prisma generate

RUN chmod +x start.sh

# Create user
RUN useradd --create-home --shell /bin/bash app

# Create and set permissions
RUN mkdir -p /app/.prisma-cache && \
    chmod 755 /app/.prisma-cache

# Give ownership to app user for application files only
RUN chown -R app:app /app

# 🔥 CRITICAL FIX: Give app user write access to Prisma package
RUN chmod -R 777 /usr/local/lib/python3.11/site-packages/prisma

# Switch to non-root user
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["bash", "./start.sh"]