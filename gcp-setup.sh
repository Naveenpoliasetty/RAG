#!/bin/bash

# GCP-specific setup script
# Run this from your LOCAL machine to configure GCP resources

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

echo "=========================================="
echo "🌐 GCP Setup for Resume RAG API"
echo "=========================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI is not installed"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

log_success "gcloud CLI found"

# Get project info
log_info "Current GCP project:"
gcloud config get-value project
echo ""

read -p "Is this the correct project? (yes/no): " correct_project
if [ "$correct_project" != "yes" ]; then
    log_info "Available projects:"
    gcloud projects list
    echo ""
    read -p "Enter project ID: " project_id
    gcloud config set project "$project_id"
fi

PROJECT_ID=$(gcloud config get-value project)
log_success "Using project: $PROJECT_ID"
echo ""

# Get instance details
log_info "Please provide your instance details:"
read -p "Instance name: " INSTANCE_NAME
read -p "Zone (e.g., us-central1-a): " ZONE

# Check if instance exists
log_info "Checking if instance exists..."
if gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" &> /dev/null; then
    log_success "Instance found: $INSTANCE_NAME"
    
    # Get instance details
    EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    log_info "External IP: $EXTERNAL_IP"
else
    log_error "Instance not found: $INSTANCE_NAME"
    echo ""
    read -p "Would you like to create a new instance? (yes/no): " create_instance
    
    if [ "$create_instance" = "yes" ]; then
        log_info "Creating new N2 instance..."
        
        # Get machine type
        echo "Select machine type:"
        echo "1) n2-standard-2 (2 vCPUs, 8 GB RAM) - ~$60/month"
        echo "2) n2-standard-4 (4 vCPUs, 16 GB RAM) - ~$120/month"
        echo "3) n2-standard-8 (8 vCPUs, 32 GB RAM) - ~$240/month"
        read -p "Choice (1-3): " machine_choice
        
        case $machine_choice in
            1) MACHINE_TYPE="n2-standard-2" ;;
            2) MACHINE_TYPE="n2-standard-4" ;;
            3) MACHINE_TYPE="n2-standard-8" ;;
            *) MACHINE_TYPE="n2-standard-4" ;;
        esac
        
        # Create instance
        gcloud compute instances create "$INSTANCE_NAME" \
            --zone="$ZONE" \
            --machine-type="$MACHINE_TYPE" \
            --boot-disk-size=50GB \
            --boot-disk-type=pd-ssd \
            --image-family=ubuntu-2204-lts \
            --image-project=ubuntu-os-cloud \
            --tags=http-server,https-server \
            --metadata=startup-script='#!/bin/bash
                apt-get update
                apt-get install -y git curl
            '
        
        log_success "Instance created!"
        
        # Get external IP
        EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
        log_info "External IP: $EXTERNAL_IP"
    else
        log_error "Cannot proceed without an instance"
        exit 1
    fi
fi

echo ""

# Ask about persistent disk
read -p "Do you want to create a persistent disk for Qdrant? (yes/no): " create_disk

if [ "$create_disk" = "yes" ]; then
    read -p "Disk size in GB (e.g., 100, 200, 500): " DISK_SIZE
    DISK_NAME="${INSTANCE_NAME}-qdrant-data"
    
    log_info "Creating persistent disk: $DISK_NAME"
    
    gcloud compute disks create "$DISK_NAME" \
        --size="${DISK_SIZE}GB" \
        --type=pd-ssd \
        --zone="$ZONE"
    
    log_success "Disk created: $DISK_NAME"
    
    log_info "Attaching disk to instance..."
    gcloud compute instances attach-disk "$INSTANCE_NAME" \
        --disk="$DISK_NAME" \
        --zone="$ZONE"
    
    log_success "Disk attached!"
    log_warning "You'll need to format and mount this disk after SSH'ing into the instance"
    echo "The deploy.sh script will help you with this."
fi

echo ""

# Configure firewall rules
log_info "Configuring firewall rules..."

# Check if rule exists
if gcloud compute firewall-rules describe allow-resume-api &> /dev/null; then
    log_warning "Firewall rule 'allow-resume-api' already exists"
    read -p "Update it? (yes/no): " update_rule
    
    if [ "$update_rule" = "yes" ]; then
        gcloud compute firewall-rules delete allow-resume-api --quiet
    else
        log_info "Skipping firewall rule creation"
    fi
fi

if ! gcloud compute firewall-rules describe allow-resume-api &> /dev/null; then
    gcloud compute firewall-rules create allow-resume-api \
        --allow=tcp:8000,tcp:80,tcp:443 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=http-server,https-server \
        --description="Allow HTTP/HTTPS and FastAPI traffic"
    
    log_success "Firewall rule created!"
fi

echo ""

# Optional: Create firewall rule for Qdrant (not recommended for production)
read -p "Allow external access to Qdrant dashboard (port 6333)? (yes/no): " allow_qdrant

if [ "$allow_qdrant" = "yes" ]; then
    log_warning "This will expose Qdrant publicly. Only do this for testing!"
    
    gcloud compute firewall-rules create allow-qdrant \
        --allow=tcp:6333 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=http-server \
        --description="Allow Qdrant dashboard access (TESTING ONLY)"
    
    log_success "Qdrant firewall rule created"
    log_warning "Remember to remove this rule in production!"
fi

echo ""
echo "=========================================="
echo "✅ GCP Setup Complete!"
echo "=========================================="
echo ""
echo "Instance Details:"
echo "  Name:        $INSTANCE_NAME"
echo "  Zone:        $ZONE"
echo "  External IP: $EXTERNAL_IP"
echo ""
echo "Next Steps:"
echo "1. SSH into your instance:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo ""
echo "2. Clone your repository:"
echo "   git clone <your-repo-url>"
echo "   cd RAG"
echo ""
echo "3. Run the deployment script:"
echo "   chmod +x deploy.sh"
echo "   ./deploy.sh"
echo ""
echo "4. After deployment, access your API at:"
echo "   http://$EXTERNAL_IP:8000/docs"
echo ""
echo "=========================================="
echo ""

# Save configuration
cat > gcp-config.txt <<EOF
# GCP Configuration
PROJECT_ID=$PROJECT_ID
INSTANCE_NAME=$INSTANCE_NAME
ZONE=$ZONE
EXTERNAL_IP=$EXTERNAL_IP

# SSH Command
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE

# API URLs
API_ROOT=http://$EXTERNAL_IP:8000/
API_HEALTH=http://$EXTERNAL_IP:8000/health
API_DOCS=http://$EXTERNAL_IP:8000/docs
QDRANT_DASHBOARD=http://$EXTERNAL_IP:6333/dashboard
EOF

log_success "Configuration saved to gcp-config.txt"
echo ""

