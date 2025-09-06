# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Generate Prisma client (as root before switching users)
RUN prisma generate

# Make startup script executable (as root before switching users)
RUN chmod +x start.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# Fix Prisma cache permissions - ensure all cache directories are accessible
RUN mkdir -p /root/.cache && \
    chown -R app:app /root/.cache && \
    chmod -R 755 /root/.cache

# Also ensure any Prisma-generated files are accessible
RUN find /usr/local/lib/python3.11/site-packages -name "*prisma*" -type d -exec chown -R app:app {} \; 2>/dev/null || true

# Switch to non-root user
USER app

# Expose port (Railway will override this)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["./start.sh"]