# 🔧 Dockerfile Fixes - Using UV Package Manager

## 🐛 Issues Found

### **Issue 1: Incorrect pip install syntax**
```dockerfile
# ❌ Wrong
pip install --no-cache-dir -r uv sync
```

**Problem:** This tries to install a package called "uv sync" from requirements file, which doesn't exist.

**Fix:** Install `uv` first, then use `uv sync` to install dependencies:
```dockerfile
# ✅ Correct
RUN pip install --no-cache-dir uv
RUN uv sync --frozen
```

---

### **Issue 2: Missing dependency files**
```dockerfile
# ❌ Wrong - removed COPY but still tried to use requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
```

**Problem:** You removed the COPY command but the RUN command still referenced the file.

**Fix:** Copy the necessary files for uv:
```dockerfile
# ✅ Correct
COPY pyproject.toml .
COPY uv.lock .
COPY setup.py .
```

---

### **Issue 3: Wrong order of operations**
```dockerfile
# ❌ Wrong - tried to install before copying files
RUN uv pip install -e .
COPY src/ ./src/
```

**Problem:** Can't install package in editable mode before copying the source code.

**Fix:** Copy files first, then install:
```dockerfile
# ✅ Correct
COPY pyproject.toml .
COPY uv.lock .
COPY setup.py .
RUN uv sync --frozen
COPY src/ ./src/
```

---

### **Issue 4: Qdrant healthcheck causing "unhealthy" status**

**Problem:** Docker Compose was checking Qdrant health even though healthcheck was commented out.

**Fix:** Removed the commented healthcheck section entirely.

---

## ✅ Fixed Dockerfile.api

```dockerfile
# Production Dockerfile for FastAPI Resume Parser
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including lxml and scipy requirements
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better caching
COPY pyproject.toml .
COPY uv.lock .
COPY setup.py .

# Install uv (fast Python package installer)
RUN pip install --no-cache-dir uv

# Install Python dependencies using uv
RUN uv sync --frozen

# Copy application code
COPY src/ ./src/
COPY main.py .

# Create uploads directory
RUN mkdir -p /app/uploads && chmod 777 /app/uploads

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "src.apis.parser_resume:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

## 🎯 Key Changes

1. ✅ **Install uv first:** `pip install uv`
2. ✅ **Copy dependency files:** `pyproject.toml`, `uv.lock`, `setup.py`
3. ✅ **Use uv sync:** `uv sync --frozen` (uses lockfile for reproducible builds)
4. ✅ **Correct order:** Copy dependencies → Install → Copy code
5. ✅ **Fixed docker-compose:** Removed commented healthcheck from Qdrant

---

## 🚀 Benefits of Using UV

- ⚡ **10-100x faster** than pip
- 🔒 **Reproducible builds** with uv.lock
- 📦 **Better dependency resolution**
- 💾 **Smaller Docker layers** with better caching

---

## 📋 Next Steps

1. Commit the fixed files
2. Push to trigger CI/CD
3. Watch deployment succeed!

