# 🚀 Deploy Your Resume RAG API NOW

## Your Configuration

Based on your requirements:
- ✅ **No persistent disk** - Using Docker volumes
- ✅ **External IP only** - No domain/SSL
- ✅ **Placeholder API key** - Update later with real key
- ✅ **Port 8000 direct** - No Nginx
- ✅ **FastAPI + Qdrant only** - Minimal setup
- ✅ **No monitoring** - Keep it simple

---

## 🎯 Deploy in 3 Steps (5 minutes)

### Step 1: SSH into Your GCP Instance

```bash
gcloud compute ssh your-instance-name --zone=your-zone
```

### Step 2: Clone Repository

```bash
cd ~
git clone <your-repository-url>
cd RAG
```

### Step 3: Run Deployment

```bash
chmod +x deploy.sh
./deploy.sh
```

**That's it!** The script will:
- ✅ Install Docker
- ✅ Configure environment (with placeholder API key)
- ✅ Setup firewall (port 8000)
- ✅ Build and start services
- ✅ Verify deployment

---

## ⚠️ Important: Update Your API Key

After deployment, you MUST update the OpenAI API key:

```bash
# Edit the .env file
nano .env

# Replace this line:
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# With your actual key:
OPENAI_API_KEY=sk-proj-YOUR_ACTUAL_KEY_HERE

# Save and exit (Ctrl+X, Y, Enter)

# Restart services
docker compose -f docker-compose.prod.yml restart
```

---

## 🧪 Test Your Deployment

### 1. Check Services

```bash
docker ps
```

You should see:
- `resume-api` (running)
- `qdrant-db` (running)

### 2. Test Health

```bash
# Get your external IP
curl ifconfig.me

# Test FastAPI
curl http://localhost:8000/health

# Test Qdrant
curl http://localhost:6333/health
```

### 3. Open API Docs

```bash
# Get your IP
EXTERNAL_IP=$(curl -s ifconfig.me)
echo "API Docs: http://$EXTERNAL_IP:8000/docs"
```

Open that URL in your browser!

---

## 🔌 Your API Endpoints

After deployment:

| Endpoint | URL |
|----------|-----|
| **API Docs** | `http://YOUR_IP:8000/docs` |
| **Health Check** | `http://YOUR_IP:8000/health` |
| **Parse Resume** | `http://YOUR_IP:8000/parse_resume` |
| **Qdrant Dashboard** | `http://YOUR_IP:6333/dashboard` |

---

## 🛠️ Daily Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart services
docker compose -f docker-compose.prod.yml restart

# Stop services
docker compose -f docker-compose.prod.yml down

# Start services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker ps
```

Or use Make commands:

```bash
make logs          # View logs
make restart       # Restart
make status        # Check status
make health        # Health check
```

---

## 📝 Parse a Resume

### Using curl:

```bash
curl -X POST "http://YOUR_IP:8000/parse_resume" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/resume.pdf"
```

### Using API Docs:

1. Open `http://YOUR_IP:8000/docs`
2. Click on `/parse_resume`
3. Click "Try it out"
4. Upload a resume file
5. Click "Execute"

---

## 🐛 Troubleshooting

### Services won't start?

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs

# Check disk space
df -h

# Restart
docker compose -f docker-compose.prod.yml restart
```

### Can't access API externally?

```bash
# Check firewall
sudo ufw status

# Should show:
# 8000/tcp    ALLOW       Anywhere

# If not, add rule:
sudo ufw allow 8000/tcp
```

### API returns errors?

```bash
# Check if you updated the API key
cat .env | grep OPENAI_API_KEY

# If still placeholder, update it:
nano .env
# Then restart:
docker compose -f docker-compose.prod.yml restart
```

---

## 💾 Backup Your Data

### Create Backup

```bash
# Backup Qdrant data
docker compose -f docker-compose.prod.yml down
sudo tar -czf qdrant-backup-$(date +%Y%m%d).tar.gz \
  /var/lib/docker/volumes/rag_qdrant-data
docker compose -f docker-compose.prod.yml up -d
```

### Restore Backup

```bash
docker compose -f docker-compose.prod.yml down
sudo tar -xzf qdrant-backup-YYYYMMDD.tar.gz -C /
docker compose -f docker-compose.prod.yml up -d
```

---

## 🔄 Update Your Deployment

```bash
# Pull latest code
cd ~/RAG
git pull

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 📊 Monitor Your Services

### Check Resource Usage

```bash
# Container stats
docker stats

# Disk usage
df -h

# Memory usage
free -h
```

### View Logs

```bash
# All logs
docker compose -f docker-compose.prod.yml logs -f

# FastAPI only
docker compose -f docker-compose.prod.yml logs -f fastapi

# Qdrant only
docker compose -f docker-compose.prod.yml logs -f qdrant
```

---

## 🎓 Next Steps (Optional)

### 1. Add Persistent Disk

If you want to add a persistent disk later:

```bash
# Create and attach disk in GCP Console
# Then format and mount:
sudo mkfs.ext4 /dev/sdb
sudo mkdir -p /mnt/qdrant-data
sudo mount /dev/sdb /mnt/qdrant-data

# Update docker-compose.prod.yml
# Uncomment the persistent disk section

# Restart services
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### 2. Add SSL/HTTPS

If you get a domain name:

```bash
# Install certbot
sudo apt-get install -y certbot

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Enable nginx in docker-compose.prod.yml
# Update nginx.conf with your domain
# Restart services
```

### 3. Add Monitoring

If you want monitoring later:

```bash
# See DEPLOYMENT.md for Prometheus/Grafana setup
```

---

## ✅ Deployment Checklist

- [ ] SSH into GCP instance
- [ ] Clone repository
- [ ] Run `./deploy.sh`
- [ ] Update OpenAI API key in `.env`
- [ ] Restart services
- [ ] Test health endpoints
- [ ] Open API docs in browser
- [ ] Test resume parsing

---

## 🆘 Need Help?

**Check logs:**
```bash
docker compose -f docker-compose.prod.yml logs
```

**Check status:**
```bash
docker ps
make status
```

**Full documentation:**
- Quick guide: `START_HERE.md`
- Step-by-step: `STEP_BY_STEP.md`
- Complete guide: `DEPLOYMENT.md`

---

## 🎉 You're Done!

Your Resume RAG API is now deployed and running!

**Access your API:**
```bash
# Get your IP
curl ifconfig.me

# Open in browser:
# http://YOUR_IP:8000/docs
```

**Remember to:**
1. ✅ Update the OpenAI API key
2. ✅ Test the API
3. ✅ Bookmark the API docs URL
4. ✅ Set up regular backups

---

**Happy parsing! 🚀**

