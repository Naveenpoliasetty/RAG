# 🚀 CI/CD Setup Guide - Quick Reference

## ✅ Setup Checklist

- [ ] Generate SSH key pair
- [ ] Add public key to VM
- [ ] Add secrets to GitHub
- [ ] Create workflow files
- [ ] Test deployment
- [ ] Verify health checks

---

## 📋 Step-by-Step Setup

### **Step 1: Generate SSH Key (Local Machine)**

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github-actions-deploy -N ""

# View private key (for GitHub secret)
cat ~/.ssh/github-actions-deploy

# View public key (for VM)
cat ~/.ssh/github-actions-deploy.pub
```

---

### **Step 2: Add Public Key to VM**

```bash
# Copy public key to VM
gcloud compute scp ~/.ssh/github-actions-deploy.pub resume-ai-ml-server:~/ \
  --zone=northamerica-northeast2-c

# SSH to VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c

# On VM: Add to authorized_keys
cat ~/github-actions-deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
rm ~/github-actions-deploy.pub
exit
```

---

### **Step 3: Add GitHub Secrets**

Go to: `https://github.com/YOUR_USERNAME/ResumeAI/settings/secrets/actions`

**Add these secrets:**

| Secret Name | Value | How to Get |
|-------------|-------|------------|
| `SSH_PRIVATE_KEY` | Private key content | `cat ~/.ssh/github-actions-deploy` |
| `VM_HOST` | `34.130.75.211` | Your VM's external IP |
| `VM_USER` | `hemanthsrinivas` | Your SSH username |

---

### **Step 4: Commit and Push Workflow Files**

```bash
cd /Users/hemanthsrinivas/ResumeAI/RAG

# Check workflow files exist
ls -la .github/workflows/

# Add to git
git add .github/

# Commit
git commit -m "Add CI/CD pipeline with GitHub Actions"

# Push
git push origin pipelines/data_scraping_pipepline
```

---

### **Step 5: Test Deployment**

#### **Option 1: Push to Trigger**
```bash
# Make a small change
echo "# CI/CD Test" >> README.md

# Commit and push
git add README.md
git commit -m "Test CI/CD pipeline"
git push origin pipelines/data_scraping_pipepline
```

#### **Option 2: Manual Trigger**
1. Go to GitHub repository
2. Click **Actions** tab
3. Select **Deploy to GCP VM**
4. Click **Run workflow**
5. Select branch and click **Run workflow**

---

### **Step 6: Monitor Deployment**

1. Go to **Actions** tab in GitHub
2. Click on the running workflow
3. Watch the deployment progress
4. Check deployment summary

---

## 🔍 Verification Commands

### **Check GitHub Actions Status**

```bash
# View workflow runs (requires GitHub CLI)
gh run list

# View specific run
gh run view <run-id>

# Watch live logs
gh run watch
```

### **Check VM Status**

```bash
# SSH to VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c

# Check containers
docker ps

# Check logs
docker logs resume-api --tail=50
docker logs qdrant-db --tail=50

# Check health
curl http://localhost:8000/health
curl http://localhost:6333/health
```

### **Check from Local Machine**

```bash
# Check API health
curl http://34.130.75.211:8000/health

# Check Qdrant health
curl http://34.130.75.211:6333/health

# Open in browser
open http://34.130.75.211:8000/docs
open http://34.130.75.211:6333/dashboard
```

---

## 🎯 What Happens on Each Push

```
1. GitHub detects push to main/pipeline branch
2. GitHub Actions workflow starts
3. Workflow checks out code
4. Workflow SSHs to VM
5. VM pulls latest code from GitHub
6. VM stops Docker containers
7. VM rebuilds Docker images
8. VM starts containers
9. Workflow runs health checks
10. Workflow reports success/failure
```

---

## 🔧 Troubleshooting

### **Deployment Fails: SSH Connection**

**Problem:** `Permission denied (publickey)`

**Solution:**
```bash
# Verify public key is on VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c
cat ~/.ssh/authorized_keys | grep github-actions

# Re-add if missing
cat ~/github-actions-deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

---

### **Deployment Fails: Git Pull**

**Problem:** `error: Your local changes would be overwritten`

**Solution:**
```bash
# SSH to VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c

# Reset to remote state
cd ~/RAG
git fetch origin
git reset --hard origin/pipelines/data_scraping_pipepline
```

---

### **Deployment Fails: Docker Build**

**Problem:** Docker build errors

**Solution:**
```bash
# SSH to VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c

# Check Docker logs
cd ~/RAG
docker compose -f docker-compose.prod.yml logs

# Rebuild manually
docker compose -f docker-compose.prod.yml build --no-cache
```

---

### **Health Check Fails**

**Problem:** Health endpoints return errors

**Solution:**
```bash
# Check if containers are running
docker ps

# Check container logs
docker logs resume-api --tail=100

# Check if ports are open
sudo netstat -tulpn | grep -E '(8000|6333)'

# Test locally on VM
curl http://localhost:8000/health
```

---

## 📊 Monitoring & Logs

### **View GitHub Actions Logs**

1. Go to repository → **Actions** tab
2. Click on workflow run
3. Click on job name
4. Expand steps to see logs

### **View VM Logs**

```bash
# SSH to VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c

# View Docker logs
docker logs resume-api --tail=100 -f
docker logs qdrant-db --tail=100 -f

# View system logs
journalctl -u docker -f
```

---

## 🔐 Security Best Practices

✅ **SSH Key Management**
- Use dedicated SSH key for CI/CD
- Never commit private keys to repository
- Rotate keys periodically

✅ **GitHub Secrets**
- Store all sensitive data as secrets
- Never log secret values
- Use environment-specific secrets

✅ **VM Security**
- Keep SSH key authentication only (no passwords)
- Restrict firewall rules to necessary ports
- Keep system and Docker updated

---

## 🚀 Advanced Features

### **Add Slack Notifications**

Add to workflow:
```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### **Add Rollback on Failure**

Add to workflow:
```yaml
- name: Rollback on Failure
  if: failure()
  run: |
    ssh -i ~/.ssh/deploy_key ${{ secrets.VM_USER }}@${{ secrets.VM_HOST }} << 'ENDSSH'
    cd ~/RAG
    git checkout HEAD~1
    docker compose -f docker-compose.prod.yml up -d
    ENDSSH
```

### **Add Database Backup**

Add before deployment:
```yaml
- name: Backup Database
  run: |
    ssh -i ~/.ssh/deploy_key ${{ secrets.VM_USER }}@${{ secrets.VM_HOST }} << 'ENDSSH'
    docker exec mongodb mongodump --out /backup/$(date +%Y%m%d_%H%M%S)
    ENDSSH
```

---

## 📝 Quick Commands

```bash
# View workflow files
ls -la .github/workflows/

# Test SSH connection
ssh -i ~/.ssh/github-actions-deploy hemanthsrinivas@34.130.75.211 "echo 'Connection successful'"

# Trigger deployment manually
gh workflow run deploy.yml

# View latest deployment
gh run view --web

# SSH to VM
gcloud compute ssh resume-ai-ml-server --zone=northamerica-northeast2-c

# Check deployment status
curl http://34.130.75.211:8000/health
```

---

## ✅ Success Indicators

After successful deployment, you should see:

1. ✅ Green checkmark in GitHub Actions
2. ✅ Deployment summary in Actions tab
3. ✅ Health checks passing
4. ✅ Containers running on VM
5. ✅ API responding at http://34.130.75.211:8000/health

---

## 🎉 You're Done!

Your CI/CD pipeline is now set up. Every push to your branch will automatically deploy to the VM!

**Next Steps:**
- Add automated tests
- Set up staging environment
- Add monitoring and alerts
- Configure database backups

