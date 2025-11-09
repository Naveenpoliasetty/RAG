# 📋 Step-by-Step Deployment Instructions

This is your complete step-by-step guide to deploy the Resume RAG API on your GCP N2 instance.

---

## 🎯 Overview

You'll deploy:
1. **FastAPI Server** - Resume parser API (Port 8000)
2. **Qdrant Database** - Vector database (Port 6333)

**Total Time:** 10-15 minutes

---

## ✅ Prerequisites

Before starting, ensure you have:
- [x] GCP N2 instance created and running
- [x] SSH access to the instance
- [x] OpenAI API key
- [x] Git installed on the instance

---

## 🚀 Deployment Steps

### Step 1: Connect to Your GCP Instance

```bash
# From your local machine
gcloud compute ssh your-instance-name --zone=your-zone

# Or if you have the external IP
ssh username@EXTERNAL_IP
```

**Expected Output:**
```
Welcome to Ubuntu 22.04 LTS
```

---

### Step 2: Clone the Repository

```bash
# Navigate to home directory
cd ~

# Clone your repository
git clone <your-repository-url>

# Navigate into the project
cd RAG

# Verify files are present
ls -la
```

**Expected Output:**
You should see files like:
- `deploy.sh`
- `docker-compose.prod.yml`
- `Dockerfile.api`
- `Makefile`
- etc.

---

### Step 3: Make Scripts Executable

```bash
# Make all scripts executable
chmod +x deploy.sh gcp-setup.sh test_api.sh

# Or use Make
make chmod
```

**Expected Output:**
```
Scripts are now executable!
```

---

### Step 4: Run the Automated Deployment

```bash
# Run the deployment script
./deploy.sh
```

**What the script does:**
1. ✅ Updates system packages
2. ✅ Installs Docker and Docker Compose
3. ✅ Sets up persistent disk (if available)
4. ✅ Configures environment variables
5. ✅ Sets up firewall rules
6. ✅ Builds and starts services
7. ✅ Verifies deployment

**During deployment, you'll be asked:**

#### Question 1: OpenAI API Key
```
Please provide your OpenAI API key:
OpenAI API Key: [paste your key here]
```

#### Question 2: Persistent Disk (if /dev/sdb exists)
```
Format /dev/sdb? This will ERASE all data! (yes/no):
```
- Type `yes` if this is a new disk
- Type `no` if the disk has existing data

#### Question 3: Qdrant External Access
```
Allow external access to Qdrant port 6333? (yes/no):
```
- Type `no` for production (recommended)
- Type `yes` only for testing

#### Question 4: Monitoring (optional)
```
Install monitoring stack (Prometheus/Grafana)? (yes/no):
```
- Type `yes` if you want monitoring
- Type `no` to skip (you can add later)

---

### Step 5: Verify Deployment

After the script completes, you'll see:

```
========================================
🚀 Deployment Summary
========================================
External IP: YOUR_EXTERNAL_IP
FastAPI URL: http://YOUR_EXTERNAL_IP:8000
Qdrant URL: http://YOUR_EXTERNAL_IP:6333
Qdrant Dashboard: http://YOUR_EXTERNAL_IP:6333/dashboard

Test API endpoint:
curl http://YOUR_EXTERNAL_IP:8000/docs
========================================
```

**Verify services are running:**

```bash
# Check Docker containers
docker ps

# You should see:
# - resume-api (running)
# - qdrant-db (running)
```

---

### Step 6: Test Your Deployment

#### Test 1: Health Check

```bash
# Test FastAPI health
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","service":"resume-parser-api","timestamp":...}
```

#### Test 2: Qdrant Health

```bash
# Test Qdrant health
curl http://localhost:6333/health

# Expected output:
# {"title":"qdrant - vector search engine","version":"..."}
```

#### Test 3: API Documentation

```bash
# Get your external IP
curl ifconfig.me

# Open in browser:
# http://YOUR_EXTERNAL_IP:8000/docs
```

You should see the FastAPI interactive documentation.

#### Test 4: Run Test Script

```bash
# Run comprehensive tests
./test_api.sh

# Or use Make
make test
```

---

### Step 7: Test Resume Parsing

#### Using curl:

```bash
# Upload a resume file
curl -X POST "http://localhost:8000/parse_resume" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/resume.docx"
```

#### Using the API Docs:

1. Open `http://YOUR_EXTERNAL_IP:8000/docs`
2. Click on `/parse_resume` endpoint
3. Click "Try it out"
4. Upload a resume file
5. Click "Execute"

---

## 🎉 Success! Your API is Live

Your deployment is complete! Here's what you have:

### 📍 Your URLs

```
API Root:          http://YOUR_IP:8000/
API Health:        http://YOUR_IP:8000/health
API Docs:          http://YOUR_IP:8000/docs
Parse Resume:      http://YOUR_IP:8000/parse_resume

Qdrant Dashboard:  http://YOUR_IP:6333/dashboard
Qdrant Health:     http://YOUR_IP:6333/health
```

---

## 🛠️ Daily Operations

### View Logs

```bash
# All logs
make logs

# FastAPI logs only
make logs-api

# Qdrant logs only
make logs-qdrant
```

### Check Status

```bash
# Service status
make status

# Health check
make health

# Resource usage
docker stats
```

### Restart Services

```bash
# Restart all
make restart

# Restart specific service
docker compose -f docker-compose.prod.yml restart fastapi
docker compose -f docker-compose.prod.yml restart qdrant
```

### Stop Services

```bash
# Stop all services
make down

# Or
docker compose -f docker-compose.prod.yml down
```

### Start Services

```bash
# Start all services
make up

# Or
docker compose -f docker-compose.prod.yml up -d
```

---

## 💾 Backup Your Data

### Create Backup

```bash
# Using Make
make backup

# Backups are stored in backups/ directory
ls -lh backups/
```

### Restore from Backup

```bash
# List available backups
ls backups/

# Restore specific backup
make restore BACKUP=qdrant-backup-20250108-120000.tar.gz
```

### Automated Backups

```bash
# Edit crontab
crontab -e

# Add this line for daily backups at 2 AM
0 2 * * * cd /home/YOUR_USERNAME/RAG && make backup
```

---

## 🔄 Update Your Deployment

### Update Code and Rebuild

```bash
# Pull latest code
git pull

# Rebuild and restart
make update

# Or manually
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 🐛 Troubleshooting

### Problem: Services won't start

```bash
# Check logs
make logs

# Check disk space
df -h

# Check if ports are in use
sudo netstat -tulpn | grep -E '8000|6333'
```

### Problem: Can't access API externally

```bash
# Check VM firewall
sudo ufw status

# Check if service is running
docker ps

# Test locally first
curl http://localhost:8000/health

# Check GCP firewall rules
gcloud compute firewall-rules list
```

### Problem: Out of memory

```bash
# Check resource usage
docker stats

# Reduce workers in .env
nano .env
# Change: WORKERS=1

# Restart services
make restart
```

### Problem: Qdrant data lost

```bash
# Check if volume is mounted
df -h | grep qdrant

# Restore from backup
make restore BACKUP=your-backup-file.tar.gz
```

---

## 📞 Getting Help

If you encounter issues:

1. **Check logs:** `make logs`
2. **Verify environment:** `cat .env`
3. **Check disk space:** `df -h`
4. **Review firewall:** `sudo ufw status`
5. **Test endpoints:** `make test`
6. **Check documentation:** See `DEPLOYMENT.md`

---

## 🎓 Next Steps

Now that your API is running:

1. **Set up SSL/HTTPS** (for production)
   - Get a domain name
   - Install Let's Encrypt certificate
   - Update nginx configuration

2. **Configure Monitoring**
   - Install Prometheus & Grafana
   - Set up alerts
   - Monitor API metrics

3. **Automate Backups**
   - Set up cron jobs
   - Upload to GCS bucket
   - Test restore process

4. **Add Security**
   - Implement API authentication
   - Add rate limiting
   - Restrict Qdrant access

5. **Set up CI/CD**
   - GitHub Actions for auto-deploy
   - Automated testing
   - Rollback procedures

---

## 📝 Quick Command Reference

```bash
# Deployment
./deploy.sh                    # Initial deployment

# Service Management
make up                        # Start services
make down                      # Stop services
make restart                   # Restart services
make status                    # Check status

# Monitoring
make logs                      # View all logs
make logs-api                  # View API logs
make logs-qdrant              # View Qdrant logs
make health                    # Health check

# Maintenance
make backup                    # Backup data
make restore BACKUP=file.tar.gz  # Restore data
make update                    # Update services

# Testing
make test                      # Run tests
make endpoints                 # Show all URLs

# Help
make help                      # Show all commands
```

---

## ✅ Deployment Checklist

Use this checklist to verify your deployment:

- [ ] SSH access to GCP instance working
- [ ] Repository cloned successfully
- [ ] Scripts made executable
- [ ] Deployment script completed without errors
- [ ] Docker containers running (`docker ps`)
- [ ] FastAPI health check passing
- [ ] Qdrant health check passing
- [ ] API docs accessible in browser
- [ ] Resume parsing endpoint working
- [ ] Firewall rules configured
- [ ] Environment variables set
- [ ] Backup created and tested
- [ ] Monitoring set up (optional)

---

## 🎉 Congratulations!

You've successfully deployed the Resume RAG API on GCP! 

Your API is now:
- ✅ Running in production
- ✅ Accessible via HTTP
- ✅ Backed by persistent storage
- ✅ Ready to parse resumes
- ✅ Easy to manage and monitor

**API Documentation:** `http://YOUR_IP:8000/docs`

---

**Need more help?** Check out:
- `QUICKSTART.md` - Quick reference
- `DEPLOYMENT.md` - Detailed guide
- `README_DEPLOYMENT.md` - Complete overview
- `make help` - All available commands

