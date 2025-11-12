# 📦 Why You Need `pip install -e .` (or equivalent)

## 🔍 The Problem

Your code uses **absolute imports** from the `src` package:

```python
# In src/api/parser_resume.py
from src.utils.logger import get_logger  # ❌ Won't work without package installation
```

And your Dockerfile runs:
```dockerfile
CMD ["uvicorn", "src.apis.parser_resume:app", ...]  # ❌ Won't work without package installation
```

---

## ❌ What Happens WITHOUT Package Installation

```bash
# When Docker container starts:
$ uvicorn src.apis.parser_resume:app

# Error:
ModuleNotFoundError: No module named 'src'

# Or when importing:
>>> from src.utils.logger import get_logger
ModuleNotFoundError: No module named 'src'
```

**Why?** Python doesn't know that `src` is a package unless:
1. It's installed via `pip install -e .`
2. OR `src` is in PYTHONPATH
3. OR you use relative imports

---

## ✅ Solution 1: Install Package (Recommended)

### **Current Dockerfile (CORRECT):**

```dockerfile
# Copy dependency files
COPY pyproject.toml .
COPY uv.lock .
COPY setup.py .

# Install uv
RUN pip install --no-cache-dir uv

# Copy source code
COPY src/ ./src/
COPY main.py .

# Install dependencies
RUN uv sync --frozen

# Install the package itself (CRITICAL!)
RUN uv pip install -e .
```

**What this does:**
- ✅ Installs all dependencies from `pyproject.toml`
- ✅ Installs your package in **editable mode**
- ✅ Makes `src` importable as a module
- ✅ Allows `from src.utils.logger import get_logger` to work
- ✅ Allows `uvicorn src.apis.parser_resume:app` to work

---

## ✅ Solution 2: Set PYTHONPATH (Alternative)

If you really don't want to install the package:

```dockerfile
# Set PYTHONPATH to include /app
ENV PYTHONPATH=/app:$PYTHONPATH

# Now Python can find src/ directory
```

**Pros:**
- ✅ No package installation needed
- ✅ Simpler for development

**Cons:**
- ❌ Not following Python best practices
- ❌ Package metadata not available
- ❌ Entry points won't work
- ❌ Some tools may not work correctly

---

## ✅ Solution 3: Use Relative Imports (Not Recommended)

Change all imports to relative:

```python
# Instead of:
from src.utils.logger import get_logger

# Use:
from ..utils.logger import get_logger
```

**Cons:**
- ❌ Requires changing ALL import statements
- ❌ Makes code less portable
- ❌ Harder to run individual scripts
- ❌ Still won't fix `uvicorn src.apis.parser_resume:app`

---

## 🎯 Recommended Approach

**Use Solution 1: Install the package**

### **Why?**
1. ✅ **Best practice** - Standard Python packaging
2. ✅ **Works everywhere** - Local dev, Docker, CI/CD
3. ✅ **Proper dependency management** - Package metadata available
4. ✅ **No path hacks** - No PYTHONPATH manipulation needed
5. ✅ **Tool compatibility** - Works with all Python tools

### **How `uv sync` Works:**

When you run `uv sync --frozen`:
1. ✅ Reads `pyproject.toml` and `uv.lock`
2. ✅ Installs all dependencies
3. ⚠️ **Does NOT install your package automatically**

That's why you need:
```dockerfile
RUN uv pip install -e .
```

This installs your package in **editable mode**, which:
- ✅ Makes `src` importable
- ✅ Doesn't copy files (uses them in place)
- ✅ Perfect for development and production

---

## 🧪 Test It Works

After building the Docker image:

```bash
# Build
docker build -f Dockerfile.api -t rag-test .

# Test imports work
docker run --rm rag-test python -c "from src.utils.logger import get_logger; print('✅ Import works!')"

# Test uvicorn can find the app
docker run --rm rag-test python -c "from src.apis.parser_resume import app; print('✅ App found!')"
```

---

## 📋 Summary

| Approach | Pros | Cons | Recommended? |
|----------|------|------|--------------|
| **Install package** (`pip install -e .`) | ✅ Best practice<br>✅ Works everywhere<br>✅ Proper packaging | None | ✅ **YES** |
| **PYTHONPATH** | ✅ Simple<br>✅ No installation | ❌ Not standard<br>❌ Path hacks | ⚠️ Only for quick fixes |
| **Relative imports** | ✅ No installation | ❌ Requires code changes<br>❌ Less portable | ❌ **NO** |

---

## ✅ Final Dockerfile (CORRECT)

```dockerfile
# Copy dependency files first for better caching
COPY pyproject.toml .
COPY uv.lock .
COPY setup.py .

# Install uv (fast Python package installer)
RUN pip install --no-cache-dir uv

# Copy application code (needed for package installation)
COPY src/ ./src/
COPY main.py .

# Install Python dependencies using uv
RUN uv sync --frozen

# Install the package itself (makes src modules importable)
# This is REQUIRED for imports like "from src.utils.logger import get_logger"
RUN uv pip install -e .
```

**This is the correct approach!** ✅

---

## 🚀 Why This Works

1. **`uv sync --frozen`** installs all dependencies from `pyproject.toml`
2. **`uv pip install -e .`** installs your package in editable mode
3. Now Python knows `src` is a package
4. Imports like `from src.utils.logger` work
5. Uvicorn can find `src.apis.parser_resume:app`
6. Everything works! 🎉

