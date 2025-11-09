#!/bin/bash

# ============================================================================
# Resume RAG API Deployment Script for GCP N2 Instance
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# Step 1: System Update and Prerequisites
# ============================================================================
step1_system_setup() {
    log_info "Step 1: Updating system and installing prerequisites..."
    
    sudo apt-get update
    sudo apt-get upgrade -y
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        vim \
        htop \
        net-tools
    
    log_success "System updated successfully"
}

# ============================================================================
# Step 2: Install Docker
# ============================================================================
step2_install_docker() {
    log_info "Step 2: Installing Docker..."
    
    # Check if Docker is already installed
    if command -v docker &> /dev/null; then
        log_warning "Docker is already installed"
        docker --version
        return 0
    fi
    
    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    
    # Install Docker Compose plugin
    sudo apt-get install -y docker-compose-plugin
    
    log_success "Docker installed successfully"
    log_warning "You may need to log out and back in for group changes to take effect"
}

# ============================================================================
# Step 3: Configure Persistent Disk for Qdrant (if attached)
# ============================================================================
step3_setup_persistent_disk() {
    log_info "Step 3: Storage Configuration"

    log_info "Using Docker volume for Qdrant data storage"
    log_info "Data will be stored in Docker-managed volume: qdrant-data"

    # Check if additional disk exists (in case user adds disk later)
    if [ -b /dev/sdb ]; then
        log_warning "Found /dev/sdb - an attached disk is available"
        log_info "To use this disk for Qdrant, you can configure it later"
        log_info "See DEPLOYMENT.md for persistent disk setup instructions"
    fi

    log_success "Storage configuration complete (using Docker volume)"
}

# ============================================================================
# Step 4: Clone Repository (if not already present)
# ============================================================================
step4_clone_repository() {
    log_info "Step 4: Setting up application code..."
    
    if [ -d "/home/$USER/RAG" ]; then
        log_warning "Repository directory already exists"
        cd /home/$USER/RAG
        log_info "Pulling latest changes..."
        git pull || log_warning "Could not pull latest changes (may not be a git repo)"
    else
        log_info "Please provide your repository URL:"
        read -p "Repository URL (or press Enter to skip): " repo_url
        
        if [ -n "$repo_url" ]; then
            cd /home/$USER
            git clone "$repo_url" RAG
            cd RAG
            log_success "Repository cloned"
        else
            log_warning "Skipping repository clone. Make sure code is present."
        fi
    fi
}

# ============================================================================
# Step 5: Configure Environment Variables
# ============================================================================
step5_configure_env() {
    log_info "Step 5: Configuring environment variables..."
    
    # Create .env file
    if [ -f .env ]; then
        log_warning ".env file already exists"
        read -p "Overwrite? (yes/no): " overwrite
        if [ "$overwrite" != "yes" ]; then
            return 0
        fi
    fi
    
    log_warning "Using placeholder OpenAI API key"
    log_info "You'll need to update this with your real API key later"

    cat > .env <<EOF
# OpenAI Configuration
# IMPORTANT: Replace this with your actual OpenAI API key!
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Qdrant Configuration
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334

# Application Configuration
LOG_LEVEL=INFO
WORKERS=2
EOF
    
    chmod 600 .env
    log_success "Environment variables configured"
}

# ============================================================================
# Step 6: Configure Firewall Rules
# ============================================================================
step6_configure_firewall() {
    log_info "Step 6: Configuring firewall rules..."
    
    # Install ufw if not present
    if ! command -v ufw &> /dev/null; then
        sudo apt-get install -y ufw
    fi
    
    # Configure firewall
    sudo ufw --force enable
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow ssh
    sudo ufw allow 8000/tcp  # FastAPI
    sudo ufw allow 80/tcp    # HTTP
    sudo ufw allow 443/tcp   # HTTPS
    
    # Optional: Allow Qdrant port (only if you need external access)
    read -p "Allow external access to Qdrant port 6333? (yes/no): " allow_qdrant
    if [ "$allow_qdrant" = "yes" ]; then
        sudo ufw allow 6333/tcp
        log_warning "Qdrant port 6333 is now publicly accessible!"
    fi
    
    sudo ufw status
    log_success "Firewall configured"
}

# ============================================================================
# Step 7: Build and Start Services
# ============================================================================
step7_deploy_services() {
    log_info "Step 7: Building and starting services..."
    
    # Ensure we're in the right directory
    cd /home/$USER/RAG
    
    # Build Docker images
    log_info "Building Docker images..."
    docker compose -f docker-compose.prod.yml build
    
    # Start services
    log_info "Starting services..."
    docker compose -f docker-compose.prod.yml up -d
    
    log_success "Services started"
}

# ============================================================================
# Step 8: Verify Deployment
# ============================================================================
step8_verify_deployment() {
    log_info "Step 8: Verifying deployment..."
    
    sleep 10  # Wait for services to start
    
    # Check Docker containers
    log_info "Docker containers status:"
    docker ps
    
    # Check Qdrant health
    log_info "Checking Qdrant health..."
    if curl -f http://localhost:6333/health &> /dev/null; then
        log_success "Qdrant is healthy"
    else
        log_error "Qdrant health check failed"
    fi
    
    # Check FastAPI health
    log_info "Checking FastAPI health..."
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_success "FastAPI is healthy"
    else
        log_warning "FastAPI health check failed (endpoint may not exist yet)"
    fi
    
    # Get external IP
    external_ip=$(curl -s ifconfig.me)
    
    log_success "Deployment verification complete!"
    echo
    echo "=========================================="
    echo "🚀 Deployment Summary"
    echo "=========================================="
    echo "External IP: $external_ip"
    echo "FastAPI URL: http://$external_ip:8000"
    echo "Qdrant URL: http://$external_ip:6333"
    echo "Qdrant Dashboard: http://$external_ip:6333/dashboard"
    echo
    echo "Test API endpoint:"
    echo "curl http://$external_ip:8000/docs"
    echo "=========================================="
}

# ============================================================================
# Monitoring setup removed - keeping deployment minimal
# To add monitoring later, see DEPLOYMENT.md
# ============================================================================

# ============================================================================
# Main Execution
# ============================================================================
main() {
    echo "=========================================="
    echo "🚀 Resume RAG API Deployment Script"
    echo "=========================================="
    echo
    
    log_info "Starting deployment process..."
    echo
    
    # Run all steps
    step1_system_setup
    echo
    
    step2_install_docker
    echo
    
    step3_setup_persistent_disk
    echo
    
    step4_clone_repository
    echo
    
    step5_configure_env
    echo
    
    step6_configure_firewall
    echo
    
    step7_deploy_services
    echo
    
    step8_verify_deployment
    echo

    log_success "Deployment complete! 🎉"
    echo
    echo "Useful commands:"
    echo "  - View logs: docker compose -f docker-compose.prod.yml logs -f"
    echo "  - Restart services: docker compose -f docker-compose.prod.yml restart"
    echo "  - Stop services: docker compose -f docker-compose.prod.yml down"
    echo "  - Check status: docker ps"
    echo
}

# Run main function
main

