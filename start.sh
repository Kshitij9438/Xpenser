#!/bin/bash
set -e

echo "🚀 Starting Xpenser API..."

PORT=${PORT:-8000}

# Check for DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set!"
    exit 1
fi

echo "📊 DATABASE_URL detected"

# 🔥 CRITICAL FIX: Generate Prisma client with actual DATABASE_URL
echo "🔧 Generating Prisma client for production database..."
prisma generate

# Optional: Verify database connection (but don't push schema in production)
echo "🔍 Verifying database schema..."
# Only uncomment this if you need to apply migrations:
# prisma db push --skip-generate

echo "✅ Prisma setup complete"
echo "🌟 Starting FastAPI server on port $PORT..."
exec uvicorn API_LAYER.app:app --host 0.0.0.0 --port $PORT