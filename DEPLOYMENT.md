# 🚀 GCP N2 Instance Deployment Guide

This guide provides step-by-step instructions to deploy the Resume Parser API with Qdrant vector database on a GCP N2 instance.

## 📋 Prerequisites

- GCP N2 instance created and running
- SSH access to the instance
- OpenAI API key
- (Optional) Persistent disk attached for Qdrant storage

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         GCP N2 Instance                 │
│  ┌───────────────────────────────────┐  │
│  │  Docker Network                   │  │
│  │                                   │  │
│  │  ┌─────────────┐  ┌────────────┐ │  │
│  │  │  FastAPI    │  │  Qdrant    │ │  │
│  │  │  Port 8000  │──│  Port 6333 │ │  │
│  │  └─────────────┘  └──────┬─────┘ │  │
│  │                           │       │  │
│  │                    ┌──────▼─────┐ │  │
│  │                    │ Persistent │ │  │
│  │                    │   Volume   │ │  │
│  │                    └────────────┘ │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## 🎯 Quick Start (Automated)

### Option 1: One-Command Deployment

```bash
# SSH into your GCP instance
gcloud compute ssh your-instance-name --zone=your-zone

# Clone the repository
git clone <your-repo-url>
cd RAG

# Make deployment script executable
chmod +x deploy.sh

# Run the deployment script
./deploy.sh
```

The script will guide you through:
1. System updates
2. Docker installation
3. Persistent disk setup (if available)
4. Environment configuration
5. Firewall setup
6. Service deployment
7. Health verification

---

## 📝 Manual Deployment (Step-by-Step)

### Step 1: Connect to Your Instance

```bash
# From your local machine
gcloud compute ssh your-instance-name --zone=your-zone

# Or use SSH with external IP
ssh username@EXTERNAL_IP
```

### Step 2: Update System

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y git curl vim htop
```

### Step 3: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version

# Log out and back in for group changes to take effect
exit
# SSH back in
```

### Step 4: Setup Persistent Disk (Optional but Recommended)

If you attached a persistent disk to your instance:

```bash
# Check available disks
lsblk

# Format the disk (WARNING: This erases data!)
sudo mkfs.ext4 -F /dev/sdb

# Create mount point
sudo mkdir -p /mnt/qdrant-data

# Mount the disk
sudo mount /dev/sdb /mnt/qdrant-data

# Set permissions
sudo chmod 777 /mnt/qdrant-data

# Add to fstab for auto-mount on reboot
echo '/dev/sdb /mnt/qdrant-data ext4 defaults 0 0' | sudo tee -a /etc/fstab

# Verify mount
df -h | grep qdrant
```

### Step 5: Clone Repository

```bash
cd ~
git clone <your-repo-url>
cd RAG
```

### Step 6: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add the following content:

```env
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Qdrant Configuration
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334

# Application Configuration
LOG_LEVEL=INFO
WORKERS=2
```

Save and exit (Ctrl+X, then Y, then Enter).

```bash
# Secure the .env file
chmod 600 .env
```

### Step 7: Update Docker Compose for Persistent Disk

If you're using a persistent disk, update the volume configuration:

```bash
nano docker-compose.prod.yml
```

Change the volumes section:

```yaml
volumes:
  qdrant-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/qdrant-data
```

### Step 8: Configure Firewall

```bash
# Install UFW
sudo apt-get install -y ufw

# Configure firewall rules
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8000/tcp  # FastAPI
sudo ufw allow 80/tcp    # HTTP (if using Nginx)
sudo ufw allow 443/tcp   # HTTPS (if using Nginx)

# Check status
sudo ufw status
```

**Important**: Also configure GCP firewall rules:

```bash
# From your local machine
gcloud compute firewall-rules create allow-resume-api \
  --allow=tcp:8000,tcp:80,tcp:443 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=http-server
```

### Step 9: Build and Deploy

```bash
# Build Docker images
docker compose -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### Step 10: Verify Deployment

```bash
# Get your external IP
curl ifconfig.me

# Test health endpoints
curl http://localhost:8000/health
curl http://localhost:6333/health

# From your local machine, test external access
curl http://EXTERNAL_IP:8000/health
curl http://EXTERNAL_IP:8000/docs
```

---

## 🧪 Testing the API

### Test Health Endpoint

```bash
curl http://EXTERNAL_IP:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "resume-parser-api",
  "timestamp": 1234567890.123
}
```

### Test Resume Parsing

```bash
curl -X POST "http://EXTERNAL_IP:8000/parse_resume" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/resume.docx"
```

### Access API Documentation

Open in browser:
```
http://EXTERNAL_IP:8000/docs
```

---

## 🔧 Useful Commands

### Service Management

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f

# View logs for specific service
docker compose -f docker-compose.prod.yml logs -f fastapi
docker compose -f docker-compose.prod.yml logs -f qdrant

# Restart services
docker compose -f docker-compose.prod.yml restart

# Stop services
docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (WARNING: Data loss!)
docker compose -f docker-compose.prod.yml down -v

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

### Monitoring

```bash
# Check container status
docker ps

# Check resource usage
docker stats

# Check disk usage
df -h

# Check Qdrant collections
curl http://localhost:6333/collections
```

### Backup Qdrant Data

```bash
# Create backup
sudo tar -czf qdrant-backup-$(date +%Y%m%d).tar.gz /mnt/qdrant-data

# Copy to GCS bucket (optional)
gsutil cp qdrant-backup-*.tar.gz gs://your-backup-bucket/
```

---

## 🔒 Security Best Practices

1. **Restrict Qdrant Access**: Don't expose port 6333 publicly
   ```bash
   # Remove public access to Qdrant
   sudo ufw delete allow 6333/tcp
   ```

2. **Use Environment Variables**: Never commit `.env` files
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

3. **Enable HTTPS**: Use Let's Encrypt for SSL certificates
   ```bash
   # Install Certbot
   sudo apt-get install -y certbot python3-certbot-nginx
   
   # Get certificate
   sudo certbot --nginx -d your-domain.com
   ```

4. **Regular Updates**:
   ```bash
   # Update system
   sudo apt-get update && sudo apt-get upgrade -y
   
   # Update Docker images
   docker compose -f docker-compose.prod.yml pull
   docker compose -f docker-compose.prod.yml up -d
   ```

---

## 🐛 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs

# Check disk space
df -h

# Check if ports are in use
sudo netstat -tulpn | grep -E '8000|6333'
```

### Can't Access API Externally

```bash
# Check firewall
sudo ufw status

# Check GCP firewall rules
gcloud compute firewall-rules list

# Check if service is listening
sudo netstat -tulpn | grep 8000
```

### Qdrant Data Loss

```bash
# Check if volume is mounted
df -h | grep qdrant

# Check volume permissions
ls -la /mnt/qdrant-data

# Restore from backup
sudo tar -xzf qdrant-backup-YYYYMMDD.tar.gz -C /
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Restart services
docker compose -f docker-compose.prod.yml restart

# Reduce workers in .env
WORKERS=1
```

---

## 📊 Monitoring Setup (Optional)

### Install Prometheus & Grafana

```bash
# Create monitoring directory
mkdir -p ~/monitoring
cd ~/monitoring

# Download monitoring compose file
# (Use the one from deploy.sh step 9)

# Start monitoring stack
docker compose -f docker-compose.monitoring.yml up -d

# Access Grafana
# http://EXTERNAL_IP:3000 (admin/admin)
```

---

## 🔄 CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GCP

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy to GCP
        env:
          GCP_SA_KEY: ${{ secrets.GCP_SA_KEY }}
        run: |
          echo "$GCP_SA_KEY" | gcloud auth activate-service-account --key-file=-
          gcloud compute ssh your-instance --zone=your-zone --command="
            cd ~/RAG &&
            git pull &&
            docker compose -f docker-compose.prod.yml up -d --build
          "
```

---

## 📞 Support

If you encounter issues:
1. Check logs: `docker compose -f docker-compose.prod.yml logs`
2. Verify environment variables: `cat .env`
3. Check disk space: `df -h`
4. Review firewall rules: `sudo ufw status`

---

## 📝 Next Steps

- [ ] Set up SSL/TLS with Let's Encrypt
- [ ] Configure automated backups
- [ ] Set up monitoring and alerting
- [ ] Implement rate limiting
- [ ] Add authentication/API keys
- [ ] Set up log aggregation
- [ ] Configure auto-scaling

