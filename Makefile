# Makefile for Resume RAG API Deployment

.PHONY: help build up down restart logs status clean backup restore test

# Default target
help:
	@echo "Resume RAG API - Deployment Commands"
	@echo "====================================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  make setup          - Initial setup (install dependencies)"
	@echo "  make build          - Build Docker images"
	@echo ""
	@echo "Service Management:"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make status         - Show service status"
	@echo ""
	@echo "Monitoring:"
	@echo "  make logs           - View all logs"
	@echo "  make logs-api       - View FastAPI logs"
	@echo "  make logs-qdrant    - View Qdrant logs"
	@echo "  make stats          - Show resource usage"
	@echo ""
	@echo "Maintenance:"
	@echo "  make backup         - Backup Qdrant data"
	@echo "  make restore        - Restore Qdrant data"
	@echo "  make clean          - Clean up containers and volumes"
	@echo "  make update         - Update and rebuild services"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Test API endpoints"
	@echo "  make health         - Check service health"
	@echo ""

# Setup
setup:
	@echo "Setting up environment..."
	@chmod +x deploy.sh gcp-setup.sh test_api.sh
	@./deploy.sh

# Make scripts executable
chmod:
	@echo "Making scripts executable..."
	@chmod +x deploy.sh gcp-setup.sh test_api.sh
	@echo "Scripts are now executable!"

# Build Docker images
build:
	@echo "Building Docker images..."
	docker compose -f docker-compose.prod.yml build

# Start services
up:
	@echo "Starting services..."
	docker compose -f docker-compose.prod.yml up -d
	@echo "Services started!"
	@make status

# Stop services
down:
	@echo "Stopping services..."
	docker compose -f docker-compose.prod.yml down
	@echo "Services stopped!"

# Restart services
restart:
	@echo "Restarting services..."
	docker compose -f docker-compose.prod.yml restart
	@echo "Services restarted!"

# View all logs
logs:
	docker compose -f docker-compose.prod.yml logs -f

# View FastAPI logs
logs-api:
	docker compose -f docker-compose.prod.yml logs -f fastapi

# View Qdrant logs
logs-qdrant:
	docker compose -f docker-compose.prod.yml logs -f qdrant

# Show service status
status:
	@echo "Service Status:"
	@docker ps --filter "name=resume-api" --filter "name=qdrant-db" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Show resource usage
stats:
	@echo "Resource Usage:"
	@docker stats --no-stream

# Backup Qdrant data
backup:
	@echo "Creating backup..."
	@mkdir -p backups
	@sudo tar -czf backups/qdrant-backup-$$(date +%Y%m%d-%H%M%S).tar.gz /mnt/qdrant-data 2>/dev/null || \
	 docker run --rm -v qdrant-data:/data -v $$(pwd)/backups:/backup alpine tar -czf /backup/qdrant-backup-$$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
	@echo "Backup created in backups/ directory"

# Restore Qdrant data (use: make restore BACKUP=filename.tar.gz)
restore:
	@if [ -z "$(BACKUP)" ]; then \
		echo "Error: Please specify BACKUP file"; \
		echo "Usage: make restore BACKUP=qdrant-backup-YYYYMMDD-HHMMSS.tar.gz"; \
		exit 1; \
	fi
	@echo "Restoring from $(BACKUP)..."
	@make down
	@sudo tar -xzf backups/$(BACKUP) -C /mnt/qdrant-data 2>/dev/null || \
	 docker run --rm -v qdrant-data:/data -v $$(pwd)/backups:/backup alpine tar -xzf /backup/$(BACKUP) -C /data
	@make up
	@echo "Restore complete!"

# Clean up
clean:
	@echo "Cleaning up..."
	@read -p "This will remove all containers and volumes. Continue? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker compose -f docker-compose.prod.yml down -v; \
		echo "Cleanup complete!"; \
	else \
		echo "Cleanup cancelled."; \
	fi

# Update and rebuild
update:
	@echo "Updating services..."
	git pull
	docker compose -f docker-compose.prod.yml pull
	docker compose -f docker-compose.prod.yml up -d --build
	@echo "Update complete!"

# Test API endpoints
test:
	@echo "Testing API endpoints..."
	@echo ""
	@echo "1. Testing root endpoint..."
	@curl -s http://localhost:8000/ | jq . || echo "Failed"
	@echo ""
	@echo "2. Testing health endpoint..."
	@curl -s http://localhost:8000/health | jq . || echo "Failed"
	@echo ""
	@echo "3. Testing Qdrant health..."
	@curl -s http://localhost:6333/health | jq . || echo "Failed"
	@echo ""

# Health check
health:
	@echo "Checking service health..."
	@echo ""
	@echo "FastAPI:"
	@curl -sf http://localhost:8000/health > /dev/null && echo "✓ Healthy" || echo "✗ Unhealthy"
	@echo ""
	@echo "Qdrant:"
	@curl -sf http://localhost:6333/health > /dev/null && echo "✓ Healthy" || echo "✗ Unhealthy"
	@echo ""

# Show external IP
ip:
	@echo "External IP:"
	@curl -s ifconfig.me
	@echo ""

# Show all endpoints
endpoints:
	@echo "API Endpoints:"
	@echo "=============="
	@EXTERNAL_IP=$$(curl -s ifconfig.me); \
	echo "Root:           http://$$EXTERNAL_IP:8000/"; \
	echo "Health:         http://$$EXTERNAL_IP:8000/health"; \
	echo "Docs:           http://$$EXTERNAL_IP:8000/docs"; \
	echo "Parse Resume:   http://$$EXTERNAL_IP:8000/parse_resume"; \
	echo ""; \
	echo "Qdrant:"; \
	echo "Dashboard:      http://$$EXTERNAL_IP:6333/dashboard"; \
	echo "Health:         http://$$EXTERNAL_IP:6333/health"; \
	echo "Collections:    http://$$EXTERNAL_IP:6333/collections"

