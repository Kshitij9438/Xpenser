#!/bin/sh

# Exit on any error
set -e

echo "🚀 Starting Expense Chatbot..."

# Wait for database to be ready (if using external DB)
if [ -n "$DATABASE_URL" ]; then
    echo "📊 Waiting for database connection..."
    # You can add database health check here if needed
fi

# Generate Prisma client if needed
echo "🔧 Generating Prisma client..."
prisma generate

# Run database migrations (if any)
if [ -n "$DATABASE_URL" ]; then
    echo "🗄️ Running database migrations..."
    prisma db push --accept-data-loss || echo "⚠️ Migration failed, continuing..."
fi

# Start the application
echo "🌟 Starting FastAPI server..."
exec python app.py