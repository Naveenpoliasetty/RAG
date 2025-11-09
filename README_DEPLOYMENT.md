# 🚀 Resume RAG API - GCP Deployment Guide

Complete deployment package for deploying the Resume Parser API with Qdrant vector database on Google Cloud Platform (GCP) N2 instances.

---

## 📦 What's Included

This deployment package includes everything you need:

- ✅ Production-ready Docker configuration
- ✅ Automated deployment scripts
- ✅ Service management tools
- ✅ Health monitoring
- ✅ Backup/restore utilities
- ✅ Comprehensive documentation
- ✅ Testing scripts

---

## 🎯 Quick Start

### Prerequisites
- GCP N2 instance (created or will be created)
- OpenAI API key
- SSH access to the instance

### Three Ways to Deploy

#### 1️⃣ Fully Automated (Fastest - 5 minutes)

```bash
# From your local machine - Setup GCP resources
chmod +x gcp-setup.sh
./gcp-setup.sh

# SSH into instance
gcloud compute ssh your-instance-name --zone=your-zone

# Clone and deploy
git clone <your-repo-url>
cd RAG
chmod +x deploy.sh
./deploy.sh
```

#### 2️⃣ Semi-Automated (10 minutes)

```bash
# SSH into your existing instance
gcloud compute ssh your-instance-name --zone=your-zone

# Clone repository
git clone <your-repo-url>
cd RAG

# Run deployment script
chmod +x deploy.sh
./deploy.sh
```

#### 3️⃣ Manual (15 minutes)

Follow the detailed guide in `QUICKSTART.md`

---

## 📚 Documentation

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **README_DEPLOYMENT.md** | Overview (this file) | Start here |
| **QUICKSTART.md** | Quick start guide | Fast deployment |
| **DEPLOYMENT.md** | Complete guide | Detailed instructions |
| **DEPLOYMENT_SUMMARY.md** | Package summary | Reference |

---

## 🏗️ Architecture

```
Internet
   │
   ▼
┌─────────────────────────────────────────┐
│      GCP N2 Instance (Ubuntu 22.04)     │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │     Docker Network                │  │
│  │                                   │  │
│  │  ┌──────────────────────────────┐ │  │
│  │  │  FastAPI Container           │ │  │
│  │  │  • Resume Parser API         │ │  │
│  │  │  • Port: 8000                │ │  │
│  │  │  • Endpoints:                │ │  │
│  │  │    - /health                 │ │  │
│  │  │    - /docs                   │ │  │
│  │  │    - /parse_resume           │ │  │
│  │  └──────────┬───────────────────┘ │  │
│  │             │                      │  │
│  │             │ REST API             │  │
│  │             ▼                      │  │
│  │  ┌──────────────────────────────┐ │  │
│  │  │  Qdrant Container            │ │  │
│  │  │  • Vector Database           │ │  │
│  │  │  • Port: 6333 (REST)         │ │  │
│  │  │  • Port: 6334 (gRPC)         │ │  │
│  │  │  • Dashboard: /dashboard     │ │  │
│  │  └──────────┬───────────────────┘ │  │
│  │             │                      │  │
│  │             ▼                      │  │
│  │  ┌──────────────────────────────┐ │  │
│  │  │  Persistent Storage          │ │  │
│  │  │  • Docker Volume or          │ │  │
│  │  │  • GCP Persistent Disk       │ │  │
│  │  │    (/mnt/qdrant-data)        │ │  │
│  │  └──────────────────────────────┘ │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 📁 File Structure

```
RAG/
├── Dockerfile.api              # Production FastAPI Dockerfile
├── docker-compose.prod.yml     # Production Docker Compose
├── .dockerignore              # Docker build optimization
├── .env.example               # Environment template
├── nginx.conf                 # Nginx configuration (optional)
├── resume-api.service         # Systemd service file
│
├── deploy.sh                  # Main deployment script ⭐
├── gcp-setup.sh              # GCP resource setup script
├── test_api.sh               # API testing script
├── Makefile                  # Service management commands ⭐
│
├── QUICKSTART.md             # Quick start guide ⭐
├── DEPLOYMENT.md             # Complete deployment guide
├── DEPLOYMENT_SUMMARY.md     # Package summary
└── README_DEPLOYMENT.md      # This file
```

---

## 🔌 API Endpoints

After deployment, your API will be available at:

| Endpoint | URL | Description |
|----------|-----|-------------|
| **Root** | `http://YOUR_IP:8000/` | API information |
| **Health** | `http://YOUR_IP:8000/health` | Health check |
| **Docs** | `http://YOUR_IP:8000/docs` | Interactive API docs |
| **Parse** | `http://YOUR_IP:8000/parse_resume` | Resume parsing |
| **Qdrant** | `http://YOUR_IP:6333/dashboard` | Vector DB dashboard |

Replace `YOUR_IP` with your instance's external IP.

---

## 🛠️ Management Commands

### Using Make (Recommended)

```bash
make help          # Show all available commands
make up            # Start all services
make down          # Stop all services
make restart       # Restart services
make logs          # View all logs
make logs-api      # View FastAPI logs only
make logs-qdrant   # View Qdrant logs only
make status        # Check service status
make health        # Run health checks
make backup        # Backup Qdrant data
make restore       # Restore from backup
make update        # Update and rebuild
make test          # Test API endpoints
make endpoints     # Show all URLs
```

### Using Docker Compose

```bash
# Start services
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart
docker compose -f docker-compose.prod.yml restart

# Stop
docker compose -f docker-compose.prod.yml down
```

---

## 🧪 Testing

### Automated Testing

```bash
# Run test script
chmod +x test_api.sh
./test_api.sh

# Or use Make
make test
```

### Manual Testing

```bash
# Health check
curl http://YOUR_IP:8000/health

# API documentation
curl http://YOUR_IP:8000/

# Parse a resume
curl -X POST "http://YOUR_IP:8000/parse_resume" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/resume.docx"
```

### Browser Testing

Open in your browser:
- API Docs: `http://YOUR_IP:8000/docs`
- Qdrant Dashboard: `http://YOUR_IP:6333/dashboard`

---

## 🔒 Security

### Firewall Configuration

**VM Level (UFW):**
```bash
sudo ufw status
```

**GCP Level:**
```bash
gcloud compute firewall-rules list
```

### Best Practices

1. ✅ Keep `.env` file secure (600 permissions)
2. ✅ Don't expose Qdrant port publicly
3. ✅ Use HTTPS in production
4. ✅ Regular security updates
5. ✅ Monitor access logs
6. ✅ Use strong API keys

---

## 💾 Backup & Restore

### Create Backup

```bash
# Using Make
make backup

# Manual
sudo tar -czf backup.tar.gz /mnt/qdrant-data
```

### Restore Backup

```bash
# Using Make
make restore BACKUP=qdrant-backup-20250108.tar.gz

# Manual
sudo tar -xzf backup.tar.gz -C /mnt/qdrant-data
```

### Automated Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * cd /home/YOUR_USER/RAG && make backup
```

---

## 📊 Monitoring

### Check Status

```bash
# Service status
make status

# Resource usage
docker stats

# Disk usage
df -h

# Logs
make logs
```

### Health Checks

```bash
# All services
make health

# Individual checks
curl http://localhost:8000/health
curl http://localhost:6333/health
```

---

## 🔄 Updates & Maintenance

### Update Services

```bash
# Using Make (recommended)
make update

# Manual
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### System Updates

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### Clean Up

```bash
# Remove unused Docker resources
docker system prune -a

# Full cleanup (WARNING: removes data)
make clean
```

---

## 🐛 Troubleshooting

### Common Issues

**Services won't start:**
```bash
make logs              # Check logs
df -h                  # Check disk space
docker ps -a           # Check container status
```

**Can't access externally:**
```bash
sudo ufw status        # Check VM firewall
gcloud compute firewall-rules list  # Check GCP firewall
curl http://localhost:8000/health   # Test locally
```

**High memory usage:**
```bash
docker stats           # Check resource usage
make restart           # Restart services
```

### Getting Help

1. Check logs: `make logs`
2. Verify config: `cat .env`
3. Check disk: `df -h`
4. Test locally: `curl http://localhost:8000/health`
5. Review docs: `DEPLOYMENT.md`

---

## 📈 Scaling

### Vertical Scaling
- Upgrade to larger instance (n2-standard-8)
- Increase persistent disk size
- Add more workers in `.env`

### Horizontal Scaling
- Deploy multiple API instances
- Use GCP Load Balancer
- Consider managed Qdrant

---

## 🎓 Next Steps

After successful deployment:

1. **SSL/HTTPS** - Set up Let's Encrypt
2. **Monitoring** - Install Prometheus/Grafana
3. **CI/CD** - Automate deployments
4. **Authentication** - Add API keys
5. **Rate Limiting** - Protect your API
6. **Logging** - Set up log aggregation
7. **Backups** - Automate with cron

---

## 📞 Support

### Documentation
- Quick Start: `QUICKSTART.md`
- Full Guide: `DEPLOYMENT.md`
- Summary: `DEPLOYMENT_SUMMARY.md`

### Commands
- Help: `make help`
- Status: `make status`
- Logs: `make logs`
- Test: `make test`

### Debugging
```bash
# Check everything
make status
make health
make logs
docker ps
df -h
```

---

## ✅ Deployment Checklist

- [ ] GCP instance created
- [ ] Persistent disk attached (optional)
- [ ] Firewall rules configured
- [ ] Repository cloned
- [ ] Environment variables set
- [ ] Services deployed
- [ ] Health checks passing
- [ ] API accessible externally
- [ ] Backups configured
- [ ] Monitoring set up

---

## 🎉 Success!

Once deployed, you'll have:
- ✅ Production-ready API server
- ✅ Persistent vector database
- ✅ Health monitoring
- ✅ Easy management tools
- ✅ Backup capabilities
- ✅ Comprehensive docs

**Your API is live at:** `http://YOUR_IP:8000/docs`

---

## 📝 Quick Reference

```bash
# Deploy
./deploy.sh

# Start
make up

# Stop
make down

# Logs
make logs

# Status
make status

# Health
make health

# Backup
make backup

# Update
make update

# Help
make help
```

---

**Version:** 1.0.0  
**Last Updated:** 2025-11-08  
**Tested On:** GCP N2 instances, Ubuntu 22.04 LTS

---

**Ready to deploy?** Start with `./deploy.sh` or follow `QUICKSTART.md`! 🚀

