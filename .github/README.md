# 🚀 CI/CD Pipeline Documentation

## Overview

This repository uses GitHub Actions for automated testing and deployment to GCP VM.

## Workflows

### 1. **Deploy to GCP VM** (`deploy.yml`)

**Triggers:**
- Push to `main` branch
- Push to `pipelines/data_scraping_pipepline` branch
- Manual trigger via GitHub Actions UI

**Steps:**
1. ✅ Checkout code
2. ✅ Setup SSH connection to VM
3. ✅ Pull latest changes on VM
4. ✅ Rebuild Docker containers
5. ✅ Restart services
6. ✅ Run health checks
7. ✅ Generate deployment summary

**Secrets Required:**
- `SSH_PRIVATE_KEY` - Private SSH key for VM access
- `VM_HOST` - VM external IP address
- `VM_USER` - SSH username for VM

---

### 2. **Run Tests** (`test.yml`)

**Triggers:**
- Push to main or pipeline branches
- Pull requests

**Steps:**
1. ✅ Setup Python 3.11
2. ✅ Install dependencies
3. ✅ Run linting (optional)
4. ✅ Run tests

---

## Setup Instructions

### 1. Generate SSH Key

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github-actions-deploy -N ""
```

### 2. Add Public Key to VM

```bash
# Copy to VM
gcloud compute scp ~/.ssh/github-actions-deploy.pub resume-ai-ml-server:~/ --zone=northamerica-northeast2-c

# SSH to VM and add to authorized_keys
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c
cat ~/github-actions-deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 3. Add Secrets to GitHub

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add:
- `SSH_PRIVATE_KEY` - Content of `~/.ssh/github-actions-deploy`
- `VM_HOST` - Your VM's external IP
- `VM_USER` - Your SSH username

### 4. Test Deployment

Push to main branch or trigger manually:
- Go to **Actions** tab
- Select **Deploy to GCP VM**
- Click **Run workflow**

---

## Deployment Flow

```
┌─────────────────┐
│  Push to GitHub │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GitHub Actions  │
│   Triggered     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SSH to VM      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Git Pull       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Docker Rebuild  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Restart Services│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Health Checks   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   ✅ Success    │
└─────────────────┘
```

---

## Monitoring Deployments

### View Deployment Status

1. Go to **Actions** tab in GitHub
2. Click on latest workflow run
3. View logs and deployment summary

### Check Services

After deployment:
- **API Health:** http://34.130.75.211:8000/health
- **API Docs:** http://34.130.75.211:8000/docs
- **Qdrant Dashboard:** http://34.130.75.211:6333/dashboard

### SSH to VM

```bash
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c
```

### Check Container Status

```bash
cd ~/RAG
docker ps
docker logs resume-api --tail=50
docker logs qdrant-db --tail=50
```

---

## Troubleshooting

### Deployment Fails

1. Check GitHub Actions logs
2. SSH to VM and check:
   ```bash
   cd ~/RAG
   docker ps
   docker logs resume-api
   ```

### Health Check Fails

```bash
# On VM
curl http://localhost:8000/health
curl http://localhost:6333/health
```

### SSH Connection Issues

1. Verify SSH key is added to VM
2. Check `SSH_PRIVATE_KEY` secret in GitHub
3. Verify VM firewall allows SSH (port 22)

---

## Manual Deployment

If CI/CD fails, deploy manually:

```bash
# SSH to VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c

# Pull changes
cd ~/RAG
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Check status
docker ps
curl http://localhost:8000/health
```

---

## Security Notes

- ✅ SSH private key is stored as GitHub secret (encrypted)
- ✅ Only authorized branches can trigger deployment
- ✅ VM uses SSH key authentication (no passwords)
- ✅ Firewall rules restrict access to necessary ports only

---

## Future Improvements

- [ ] Add automated tests
- [ ] Add staging environment
- [ ] Add rollback mechanism
- [ ] Add Slack/Discord notifications
- [ ] Add performance monitoring
- [ ] Add database backup before deployment

