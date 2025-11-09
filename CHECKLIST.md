# ✅ Deployment Checklist

Use this checklist to track your deployment progress.

---

## 📋 Pre-Deployment

### GCP Setup
- [ ] GCP N2 instance created
- [ ] Instance is running
- [ ] External IP assigned
- [ ] SSH access configured
- [ ] Can connect via `gcloud compute ssh`

### Local Preparation
- [ ] Repository URL ready
- [ ] Know your instance name
- [ ] Know your zone (e.g., us-central1-a)
- [ ] Have terminal/SSH client ready

---

## 🚀 Deployment Steps

### Step 1: Connect
- [ ] SSH into GCP instance
- [ ] Verify you're in the home directory
- [ ] Internet connection working

### Step 2: Clone Repository
- [ ] Repository cloned successfully
- [ ] Navigated into RAG directory
- [ ] Can see deployment files (`ls -la`)

### Step 3: Run Deployment
- [ ] Made deploy.sh executable (`chmod +x deploy.sh`)
- [ ] Started deployment (`./deploy.sh`)
- [ ] Script completed without errors
- [ ] Saw "Deployment complete! 🎉" message

---

## 🔧 Post-Deployment Configuration

### Update API Key
- [ ] Opened .env file (`nano .env`)
- [ ] Replaced placeholder API key with real key
- [ ] Saved file (Ctrl+X, Y, Enter)
- [ ] Restarted services (`docker compose -f docker-compose.prod.yml restart`)

### Verify Services
- [ ] Checked Docker containers (`docker ps`)
- [ ] See `resume-api` container running
- [ ] See `qdrant-db` container running
- [ ] Both containers show "Up" status

---

## 🧪 Testing

### Health Checks
- [ ] FastAPI health check passes (`curl http://localhost:8000/health`)
- [ ] Qdrant health check passes (`curl http://localhost:6333/health`)
- [ ] Got external IP (`curl ifconfig.me`)
- [ ] Saved external IP for reference

### Browser Access
- [ ] Opened API docs in browser (`http://YOUR_IP:8000/docs`)
- [ ] API docs page loads correctly
- [ ] Can see all endpoints listed
- [ ] Qdrant dashboard accessible (`http://YOUR_IP:6333/dashboard`)

### API Testing
- [ ] Tested root endpoint (`curl http://YOUR_IP:8000/`)
- [ ] Tested health endpoint (`curl http://YOUR_IP:8000/health`)
- [ ] Tried parse_resume endpoint in API docs
- [ ] Successfully parsed a test resume

---

## 🔒 Security

### Firewall
- [ ] Checked UFW status (`sudo ufw status`)
- [ ] Port 22 (SSH) is allowed
- [ ] Port 8000 (API) is allowed
- [ ] Verified GCP firewall rules allow port 8000

### Environment
- [ ] .env file has correct permissions (600)
- [ ] API key is not exposed in logs
- [ ] No sensitive data in git history

---

## 💾 Backup

### Initial Backup
- [ ] Created first backup (`make backup` or manual)
- [ ] Verified backup file exists
- [ ] Tested restore process (optional)
- [ ] Documented backup location

### Backup Schedule
- [ ] Decided on backup frequency (daily/weekly)
- [ ] Set up cron job for automated backups (optional)
- [ ] Tested backup script works

---

## 📊 Monitoring

### Basic Monitoring
- [ ] Know how to check logs (`make logs`)
- [ ] Know how to check status (`make status`)
- [ ] Know how to check resource usage (`docker stats`)
- [ ] Bookmarked API docs URL

### Log Management
- [ ] Viewed FastAPI logs
- [ ] Viewed Qdrant logs
- [ ] Understand log format
- [ ] Know how to tail logs (`-f` flag)

---

## 📚 Documentation

### Read Documentation
- [ ] Read `DEPLOY_NOW.md`
- [ ] Understand daily commands
- [ ] Know where to find help
- [ ] Bookmarked important docs

### Save Important Info
- [ ] Saved external IP address
- [ ] Saved API docs URL
- [ ] Saved SSH command
- [ ] Documented any custom changes

---

## 🎓 Knowledge Check

### Commands You Should Know
- [ ] How to start services (`make up` or `docker compose up`)
- [ ] How to stop services (`make down` or `docker compose down`)
- [ ] How to restart services (`make restart`)
- [ ] How to view logs (`make logs`)
- [ ] How to check status (`make status`)
- [ ] How to backup data (`make backup`)

### Troubleshooting
- [ ] Know how to check if services are running
- [ ] Know how to view error logs
- [ ] Know how to restart failed services
- [ ] Know where to find help docs

---

## 🔄 Maintenance

### Regular Tasks
- [ ] Set reminder to check logs weekly
- [ ] Set reminder to backup data regularly
- [ ] Set reminder to update system packages monthly
- [ ] Set reminder to check disk space

### Update Process
- [ ] Know how to pull latest code (`git pull`)
- [ ] Know how to rebuild services (`make update`)
- [ ] Know how to rollback if needed
- [ ] Documented update procedure

---

## 📞 Support Resources

### Documentation
- [ ] Know where `DEPLOY_NOW.md` is
- [ ] Know where `STEP_BY_STEP.md` is
- [ ] Know where `DEPLOYMENT.md` is
- [ ] Know where `INDEX.md` is

### Commands
- [ ] Tried `make help` command
- [ ] Understand Make commands
- [ ] Understand Docker Compose commands
- [ ] Can navigate documentation

---

## 🎯 Production Readiness

### Before Going Live
- [ ] Tested with multiple resume files
- [ ] Verified parsing accuracy
- [ ] Tested error handling
- [ ] Checked response times
- [ ] Verified data persistence

### Performance
- [ ] Monitored resource usage
- [ ] Checked memory consumption
- [ ] Checked disk usage
- [ ] Verified no memory leaks

### Reliability
- [ ] Tested service restart
- [ ] Tested after system reboot
- [ ] Verified data survives restart
- [ ] Tested backup/restore

---

## ✨ Optional Enhancements

### Future Improvements
- [ ] Consider adding persistent disk
- [ ] Consider adding SSL/HTTPS
- [ ] Consider adding monitoring
- [ ] Consider adding CI/CD
- [ ] Consider adding authentication
- [ ] Consider adding rate limiting

### Advanced Features
- [ ] Explored Qdrant dashboard
- [ ] Understood vector storage
- [ ] Tested collection management
- [ ] Explored API customization

---

## 🎉 Completion

### Final Checks
- [ ] All services running smoothly
- [ ] API accessible externally
- [ ] Resume parsing working
- [ ] Backups configured
- [ ] Documentation reviewed
- [ ] Team notified (if applicable)

### Success Criteria
- [ ] ✅ API responds to health checks
- [ ] ✅ Can parse resumes successfully
- [ ] ✅ Data persists across restarts
- [ ] ✅ Logs are accessible
- [ ] ✅ Backups are working
- [ ] ✅ Know how to troubleshoot

---

## 📝 Notes

Use this space to document any custom configurations or issues:

```
Date: _______________
External IP: _______________
Instance Name: _______________
Zone: _______________

Custom Changes:
- 
- 
- 

Issues Encountered:
- 
- 
- 

Solutions Applied:
- 
- 
- 

Additional Notes:
- 
- 
- 
```

---

## 🚀 Deployment Status

**Overall Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Deployment Date:** _______________

**Deployed By:** _______________

**API URL:** http://_______________:8000/docs

**Status:** [ ] Development  [ ] Testing  [ ] Production

---

## 📞 Quick Reference

### Essential Commands
```bash
# Check status
docker ps
make status

# View logs
make logs

# Restart
make restart

# Backup
make backup

# Help
make help
```

### Essential URLs
```
API Docs:     http://YOUR_IP:8000/docs
Health:       http://YOUR_IP:8000/health
Qdrant:       http://YOUR_IP:6333/dashboard
```

### Essential Files
```
Configuration:  .env
Logs:          docker compose logs
Backups:       backups/
Docs:          DEPLOY_NOW.md
```

---

**Checklist Version:** 1.0.0  
**Last Updated:** 2025-11-08

---

**Print this checklist and check off items as you complete them!** ✅

