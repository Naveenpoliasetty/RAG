#!/bin/bash

echo "Starting ZenML MLOps Environment..."

# Check if we're inside a container with docker access
if command -v docker &> /dev/null; then
    echo "📋 Checking Docker container status..."
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(zenml|qdrant|postgres)" || echo "⚠️  No service containers found"
    echo ""
fi

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if ZenML server is accessible
echo "🔍 Checking ZenML Server..."
max_retries=30
retry_count=0
zenml_ready=false
while [ $retry_count -lt $max_retries ]; do
    if curl -s http://zenml-server:8080/health > /dev/null 2>&1; then
        echo " ZenML Server is ready!"
        zenml_ready=true
        break
    fi
    echo "⏳ Waiting for ZenML Server... ($((retry_count + 1))/$max_retries)"
    sleep 2
    retry_count=$((retry_count + 1))
done

if [ "$zenml_ready" = false ]; then
    echo "❌ ZenML Server did not become ready"
    echo "   Try: docker logs zenml-server"
fi

# Check if Qdrant is accessible
echo "🔍 Checking Qdrant..."
qdrant_ready=false
if curl -s http://qdrant:6333/health > /dev/null 2>&1; then
    echo " Qdrant is ready!"
    qdrant_ready=true
    # Check Qdrant dashboard
    qdrant_response=$(curl -s http://qdrant:6333/ 2>&1)
    if echo "$qdrant_response" | grep -q "qdrant" || echo "$qdrant_response" | grep -q "404"; then
        echo "   Dashboard available at: http://localhost:6333/dashboard"
    fi
else
    echo "❌ Qdrant may not be ready yet"
    echo "   Try: docker logs zenml-qdrant"
fi

# Check if PostgreSQL is accessible
echo "🔍 Checking PostgreSQL..."
if pg_isready -h postgres -p 5432 -U zenml > /dev/null 2>&1; then
    echo " PostgreSQL is ready!"
else
    echo "⚠️  PostgreSQL may not be ready yet"
    echo "   Try: docker logs zenml-postgres"
fi

# Connect ZenML client to server
if [ "$zenml_ready" = true ]; then
    echo "🔗 Connecting ZenML client to server..."
    zenml login --url http://zenml-server:8080 --username default --password zenml --no-verify-ssl || true
else
    echo "⚠️  Skipping ZenML login - server not ready"
fi

echo ""
echo "=========================================="
echo "✨ ZenML MLOps Environment is ready!"
echo "=========================================="
echo ""
echo "📍 Service URLs (access from your host machine):"
echo "   - ZenML Server:      http://localhost:8080"
echo "   - ZenML Dashboard:   http://localhost:8080 (if available)"
echo "   - Qdrant REST API:   http://localhost:6333"
echo "   - Qdrant Dashboard:  http://localhost:6333/dashboard"
echo "   - Qdrant Health:     http://localhost:6333/health"
echo "   - PostgreSQL:       localhost:5432"
echo ""
echo "🔍 Troubleshooting:"
echo "   1. If services aren't accessible, check:"
echo "      - docker ps (all containers should be running)"
echo "      - docker logs zenml-server"
echo "      - docker logs zenml-qdrant"
echo "   2. Port forwarding should happen automatically in VS Code"
echo "      - Check the 'Ports' tab in VS Code for forwarded ports"
echo "      - Ensure ports 8080 and 6333 are listed"
echo "   3. If Qdrant dashboard shows 404:"
echo "      - Try: http://localhost:6333"
echo "      - Or use Qdrant REST API at http://localhost:6333/collections"
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

