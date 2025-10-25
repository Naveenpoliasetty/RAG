# ZenML MLOps Development Environment

This development container provides a complete MLOps environment with ZenML, PostgreSQL, and Qdrant vector database.

## Architecture

This setup includes:

1. **ZenML Server**: Orchestration and tracking for ML pipelines
2. **PostgreSQL**: Stores pipeline metadata, configurations, and tracking information
3. **Qdrant**: Vector database for storing and searching high-dimensional embeddings
4. **Development Container**: Python environment with all necessary dependencies

## Getting Started

### Prerequisites

- Docker Desktop
- Visual Studio Code
- Dev Containers extension for VS Code

### Setup

1. Open this folder in VS Code
2. When prompted, click "Reopen in Container" (or use Command Palette: "Dev Containers: Reopen in Container")
3. Wait for the containers to build and start
4. The startup script will automatically configure ZenML to connect to the server

### Services

Once the container is running, you can access:

- **ZenML Dashboard**: http://localhost:8080
  - Username: `default`
  - Password: `zenml`
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **PostgreSQL**: `localhost:5432`
  - Database: `zenml`
  - Username: `zenml`
  - Password: `zenml`

### Verify Installation

```bash
# Check ZenML status
zenml status

# List available stacks
zenml stack list

# Check service versions
zenml version
```

## Using Qdrant with ZenML

### Install Qdrant Integration

```bash
zenml integration install qdrant
```

### Example: Connecting to Qdrant

```python
from qdrant_client import QdrantClient

# Connect to Qdrant
client = QdrantClient(host="qdrant", port=6333)

# Check connection
print(client.get_collections())
```

## Example Pipeline

Create a simple ZenML pipeline:

```python
from zenml import pipeline, step

@step
def load_data() -> dict:
    """Load sample data."""
    return {"data": [1, 2, 3, 4, 5]}

@step
def process_data(data: dict) -> dict:
    """Process the data."""
    processed = {"processed": [x * 2 for x in data["data"]]}
    return processed

@pipeline
def simple_pipeline():
    """A simple pipeline."""
    data = load_data()
    process_data(data)

if __name__ == "__main__":
    simple_pipeline()
```

## Common Commands

```bash
# Connect to ZenML server (already done by startup script)
zenml connect --url http://zenml-server:8080 --username default --password zenml

# Create a new stack
zenml stack register my_stack -o default -a default

# Set active stack
zenml stack set my_stack

# List integrations
zenml integration list

# Install integrations
zenml integration install qdrant sklearn

# View pipeline runs
zenml pipeline runs list
```

## Troubleshooting

### Check Service Health

```bash
# Check if services are running
docker ps

# Check ZenML server logs
docker logs zenml-server

# Check PostgreSQL logs
docker logs zenml-postgres

# Check Qdrant logs
docker logs zenml-qdrant
```

### Reconnect to ZenML Server

```bash
zenml connect --url http://zenml-server:8080 --username default --password zenml
```

### Reset PostgreSQL Database

```bash
docker-compose down -v
docker-compose up -d
```

## Environment Variables

The following environment variables are pre-configured:

- `ZENML_SERVER_URL`: http://zenml-server:8080
- `POSTGRES_HOST`: postgres
- `POSTGRES_PORT`: 5432
- `POSTGRES_USER`: zenml
- `POSTGRES_PASSWORD`: zenml
- `POSTGRES_DB`: zenml
- `QDRANT_HOST`: qdrant
- `QDRANT_PORT`: 6333
- `QDRANT_GRPC_PORT`: 6334

## Additional Resources

- [ZenML Documentation](https://docs.zenml.io/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

