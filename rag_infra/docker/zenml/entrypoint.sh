#!/bin/bash
# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
while ! pg_isready -h sql -p 5432 -U zenml; do
    sleep 2
done

# Initialize ZenML database if not already done
if ! zenml stack list | grep -q default; then
    echo "Initializing ZenML default stack..."
    zenml init --skip-analytics
    zenml stack register local_stack -o default -a local
fi

# Keep container alive
exec "$@"