#!/bin/bash

echo "🚀 Starting ZenML MLOps Environment..."

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if ZenML server is accessible
max_retries=30
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if curl -s http://zenml-server:8080/health > /dev/null 2>&1; then
        echo "✅ ZenML Server is ready!"
        break
    fi
    echo "⏳ Waiting for ZenML Server... ($((retry_count + 1))/$max_retries)"
    sleep 2
    retry_count=$((retry_count + 1))
done

# Check if Qdrant is accessible
if curl -s http://qdrant:6333/health > /dev/null 2>&1; then
    echo "✅ Qdrant is ready!"
else
    echo "⚠️  Qdrant may not be ready yet"
fi

# Check if PostgreSQL is accessible
if pg_isready -h postgres -p 5432 -U zenml > /dev/null 2>&1; then
    echo "✅ PostgreSQL is ready!"
else
    echo "⚠️  PostgreSQL may not be ready yet"
fi

# Connect ZenML client to server
echo "🔗 Connecting ZenML client to server..."
zenml connect --url http://zenml-server:8080 --username default --password zenml --no-verify-ssl || true

echo ""
echo "=========================================="
echo "✨ ZenML MLOps Environment is ready!"
echo "=========================================="
echo ""
echo "📍 Service URLs:"
echo "   - ZenML Server:    http://localhost:8080"
echo "   - Qdrant REST API: http://localhost:6333"
echo "   - Qdrant Dashboard: http://localhost:6333/dashboard"
echo "   - PostgreSQL:      localhost:5432"
echo ""
echo "📚 Quick Start:"
echo "   - Run 'zenml status' to check connection"
echo "   - Run 'zenml stack list' to see available stacks"
echo "   - Run 'zenml integration install qdrant' for Qdrant integration"
echo ""
echo "🔐 Default Credentials:"
echo "   - ZenML: default / zenml"
echo "   - PostgreSQL: zenml / zenml"
echo ""
echo "=========================================="

