# 🚀 Quick Start Guide - GCP Deployment

## Prerequisites Checklist
- [ ] GCP N2 instance created
- [ ] SSH access configured
- [ ] OpenAI API key ready
- [ ] (Optional) Persistent disk attached

---

## 🎯 Fastest Deployment (5 Minutes)

### Step 1: Connect to Your Instance
```bash
gcloud compute ssh your-instance-name --zone=your-zone
```

### Step 2: Clone Repository
```bash
git clone <your-repo-url>
cd RAG
```

### Step 3: Run Automated Deployment
```bash
chmod +x deploy.sh
./deploy.sh
```

**That's it!** The script will handle everything automatically.

---

## 📋 Manual Deployment (15 Minutes)

### 1. Install Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
sudo apt-get install -y docker-compose-plugin
```

**Important:** Log out and back in after this step!

### 2. Setup Environment
```bash
cd ~/RAG
nano .env
```

Add:
```env
OPENAI_API_KEY=your-key-here
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
```

Save: `Ctrl+X`, `Y`, `Enter`

### 3. Configure Firewall
```bash
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 8000/tcp
```

**Also configure GCP firewall:**
```bash
# From your local machine
gcloud compute firewall-rules create allow-api \
  --allow=tcp:8000 \
  --target-tags=http-server
```

### 4. Deploy Services
```bash
docker compose -f docker-compose.prod.yml up -d
```

### 5. Verify Deployment
```bash
# Get your external IP
curl ifconfig.me

# Test the API
curl http://localhost:8000/health
```

---

## 🧪 Testing Your Deployment

### Check Service Status
```bash
docker ps
```

You should see:
- `resume-api` (running)
- `qdrant-db` (running)

### Test API Endpoints

**1. Health Check:**
```bash
curl http://localhost:8000/health
```

**2. API Documentation:**
Open in browser: `http://YOUR_EXTERNAL_IP:8000/docs`

**3. Parse a Resume:**
```bash
curl -X POST "http://localhost:8000/parse_resume" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/resume.docx"
```

### Test Qdrant

**1. Health Check:**
```bash
curl http://localhost:6333/health
```

**2. Dashboard:**
Open in browser: `http://YOUR_EXTERNAL_IP:6333/dashboard`

---

## 🔧 Common Commands

### Using Make (Recommended)
```bash
make help          # Show all commands
make status        # Check service status
make logs          # View logs
make restart       # Restart services
make health        # Health check
make endpoints     # Show all URLs
```

### Using Docker Compose
```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart services
docker compose -f docker-compose.prod.yml restart

# Stop services
docker compose -f docker-compose.prod.yml down

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 🐛 Quick Troubleshooting

### Services Won't Start
```bash
# Check logs
docker compose -f docker-compose.prod.yml logs

# Check if ports are in use
sudo netstat -tulpn | grep -E '8000|6333'
```

### Can't Access API from Outside
```bash
# Check firewall
sudo ufw status

# Check if service is running
docker ps

# Check GCP firewall rules
gcloud compute firewall-rules list
```

### Out of Disk Space
```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a
```

---

## 📊 Your Deployment URLs

After deployment, access your services at:

```
API Root:          http://YOUR_IP:8000/
API Health:        http://YOUR_IP:8000/health
API Docs:          http://YOUR_IP:8000/docs
Parse Resume:      http://YOUR_IP:8000/parse_resume

Qdrant Dashboard:  http://YOUR_IP:6333/dashboard
Qdrant Health:     http://YOUR_IP:6333/health
```

Replace `YOUR_IP` with your instance's external IP (get it with `curl ifconfig.me`)

---

## 🔒 Security Checklist

- [ ] Changed default passwords
- [ ] Configured firewall rules
- [ ] Secured `.env` file (`chmod 600 .env`)
- [ ] Restricted Qdrant port (don't expose 6333 publicly)
- [ ] Set up SSL/HTTPS (for production)
- [ ] Enabled automated backups

---

## 📞 Need Help?

1. **Check logs:** `make logs` or `docker compose -f docker-compose.prod.yml logs`
2. **Verify environment:** `cat .env`
3. **Check disk space:** `df -h`
4. **Review firewall:** `sudo ufw status`
5. **See full guide:** Read `DEPLOYMENT.md`

---

## 🎉 Next Steps

Once your deployment is working:

1. **Set up monitoring:** Run monitoring stack (see `DEPLOYMENT.md`)
2. **Configure backups:** `make backup` (schedule with cron)
3. **Add SSL/HTTPS:** Use Let's Encrypt (see `DEPLOYMENT.md`)
4. **Scale up:** Add more workers or upgrade instance
5. **CI/CD:** Set up automated deployments

---

## 💡 Pro Tips

1. **Use Make commands** - They're easier than remembering Docker Compose commands
2. **Monitor logs regularly** - `make logs-api` to catch issues early
3. **Backup before updates** - `make backup` before running `make update`
4. **Check health often** - `make health` to ensure services are running
5. **Use persistent disk** - For Qdrant data to survive instance restarts

---

## 📝 Quick Reference Card

```bash
# Start services
make up

# Check status
make status

# View logs
make logs

# Health check
make health

# Restart
make restart

# Backup data
make backup

# Update services
make update

# Get all URLs
make endpoints
```

---

**Deployment Time:** ~5 minutes (automated) or ~15 minutes (manual)

**Ready to deploy?** Run `./deploy.sh` and you're good to go! 🚀

