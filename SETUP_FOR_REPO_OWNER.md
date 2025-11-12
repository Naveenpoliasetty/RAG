# 🔐 GitHub Secrets Setup - For Repository Owner

## Quick Setup (5 minutes)

### Step 1: Go to Repository Settings

1. Open: `https://github.com/YOUR_USERNAME/ResumeAI/settings/secrets/actions`
2. Click **"New repository secret"**

---

### Step 2: Add Three Secrets

#### Secret 1: SSH_PRIVATE_KEY

**Name:** `SSH_PRIVATE_KEY`

**Value:** Copy the entire private key that I'll send you securely. It should look like:

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
...
[many lines of random characters]
...
-----END OPENSSH PRIVATE KEY-----
```

**Important:** 
- ✅ Copy the ENTIRE key including the BEGIN and END lines
- ✅ No extra spaces or newlines at the beginning or end
- ✅ Keep this secret - never share it publicly

---

#### Secret 2: VM_HOST

**Name:** `VM_HOST`

**Value:** `34.130.75.211`

This is the external IP address of our GCP VM.

---

#### Secret 3: VM_USER

**Name:** `VM_USER`

**Value:** `hemanthsrinivas`

This is the SSH username for the VM.

---

### Step 3: Verify Secrets Added

After adding all three secrets, you should see:

```
✅ SSH_PRIVATE_KEY
✅ VM_HOST
✅ VM_USER
```

---

## 🎯 What This Enables

Once these secrets are added:

1. ✅ Automatic deployment on every push to main/pipeline branches
2. ✅ GitHub Actions can SSH to the VM
3. ✅ Code is automatically pulled and deployed
4. ✅ Docker containers are rebuilt and restarted
5. ✅ Health checks verify deployment success

---

## 🔒 Security Notes

- ✅ Secrets are encrypted by GitHub
- ✅ Secrets are never exposed in logs
- ✅ Only GitHub Actions workflows can access them
- ✅ Collaborators cannot view secret values (only names)

---

## ❓ Questions?

If you have any questions about adding these secrets, let me know!

After adding them, I'll test the deployment to make sure everything works.

