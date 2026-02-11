# Use Python 3.11 image
FROM python:3.11

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PRISMA_CLIENT_ENGINE_TYPE=library \
    PRISMA_CACHE_DIR=/app/.prisma-cache

# Install system dependencies + Node (for Prisma)
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

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Generate Prisma client
RUN prisma generate

# Make startup script executable
RUN chmod +x start.sh

# Create non-root user and own app directory
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# ✅ Create Prisma cache directory owned by app
RUN mkdir -p /app/.prisma-cache \
    && chown -R app:app /app/.prisma-cache

# Fix Prisma library permissions (safe)
RUN find /usr/local/lib -path "*prisma*" -type d -exec chown -R app:app {} \; 2>/dev/null || true

# Switch to non-root user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application (force bash)
CMD ["bash", "./start.sh"]
