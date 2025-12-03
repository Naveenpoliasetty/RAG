# Qdrant Connection Issue - Root Cause Analysis

## Problem Summary

The application was failing to connect to Qdrant with error `[Errno 61] Connection refused` during FastAPI startup, even though the Qdrant server was accessible and responding correctly.

## Root Cause

The issue was caused by **environment variable configuration override**. The application has two configuration systems:

1. **YAML Config** (`src/core/config.yaml`):

   ```yaml
   qdrant:
     host: "34.130.75.211"
     port: 6333
   ```

2. **Environment Variables** (`.env` file):
   ```bash
   QDRANT_HOST=localhost  # ❌ Wrong value
   QDRANT_PORT=6333
   ```

The `settings.py` configuration loader reads the YAML file first, but then **overrides** values with environment variables if they exist (see `_override_with_env_vars()` method). This caused the application to attempt connecting to `localhost:6333` instead of `34.130.75.211:6333`.

## Why It Worked Standalone But Not in FastAPI

- The test script worked because it used the YAML config values directly
- The FastAPI application loaded environment variables first, which overrode the YAML values
- Since there was no Qdrant instance running on `localhost`, the connection was refused

## The Fix

Updated `.env` file from:

```bash
QDRANT_HOST=localhost
```

To:

```bash
QDRANT_HOST=34.130.75.211
```

## Lessons Learned

### 1. **Configuration Priority**

When using multiple configuration sources, understand the priority order:

```
Environment Variables > YAML Config > Default Values
```

### 2. **Consistency**

Keep `.env` and `config.yaml` synchronized. If you change one, update the other.

### 3. **Configuration Documentation**

The `.env.example` file should clearly document:

```bash
# For local development with Docker:
# QDRANT_HOST=localhost

# For production with remote server:
QDRANT_HOST=34.130.75.211
QDRANT_PORT=6333
```

### 4. **Debug Logging**

Added connection logging to `qdrant_manager.py` to help diagnose similar issues:

```python
logger.info(f"Connecting to Qdrant at {config.qdrant_host}:{config.qdrant_port}")
```

This makes it immediately obvious which host/port is being used.

## Verification

After the fix, the application starts successfully:

```
INFO | QdrantManager | Connecting to Qdrant at 34.130.75.211:6333
INFO | QdrantManager | Successfully connected to Qdrant
INFO | src.core.db_manager |  All database connections initialized
INFO: Application startup complete.
```

## Future Prevention

1. **Always check `.env` values** when experiencing connection issues
2. **Use the diagnostic script** (`test_qdrant_connection.py`) to isolate configuration problems
3. **Review environment variable overrides** in `settings.py` when debugging
4. **Document which config source takes precedence** in your README

## Files Modified

1. `.env` - Updated `QDRANT_HOST` to point to the correct server
2. `qdrant_manager.py` - Added basic connection logging for easier debugging

## Test Commands

To verify Qdrant connectivity in the future:

```bash
# 1. Check network connectivity
curl http://34.130.75.211:6333/

# 2. Run diagnostic test
source .venv/bin/activate
python test_qdrant_connection.py

# 3. Start the application
uvicorn src.main:app --reload --port 8000
```
