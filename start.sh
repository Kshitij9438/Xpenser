#!/bin/bash
set -e

echo "🚀 Starting Xpenser API..."

PORT=${PORT:-8000}

# Optional: log DB presence
if [ -n "$DATABASE_URL" ]; then
    echo "📊 DATABASE_URL detected"
fi

# ⚠️ Do NOT auto-run prisma db push in production
# Run migrations manually when needed

echo "🌟 Starting FastAPI server on port $PORT..."
exec uvicorn API_LAYER.app:app --host 0.0.0.0 --port $PORT
