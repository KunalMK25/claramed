# ClaraMed Windows Setup and Verification

**Last Updated:** November 11, 2026  
**Platform:** Windows 11  
**Python:** 3.11.9  
**Environment:** D:\ClaraMedEnv\venv

## Table of Contents

- [Environment Setup](#environment-setup)
- [Infrastructure Components](#infrastructure-components)
- [Database Setup](#database-setup)
- [Starting ClaraMed](#starting-claramed)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Environment Setup

### Python Virtual Environment

```powershell
# Virtual environment location
D:\ClaraMedEnv\venv

# Activate environment
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1

# Verify Python version
python --version
# Expected: Python 3.11.9
```

### Environment Variables

All configuration is stored in `.env` at the project root:

```ini
# Application
APP_ENV=development
APP_NAME=ClaraMed
APP_VERSION=1.0.0

# Database
DATABASE_URL=postgresql://claramed:claramed@localhost:5432/claramed

# Redis
REDIS_URL=redis://localhost:6379/0

# Groq AI
GROQ_API_KEY=<configured>
GROQ_MODEL=openai/gpt-oss-120b

# Tesseract OCR
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe

# Radiology AI
RADIOLOGY_MODEL_NAME=densenet121-res224-all
RADIOLOGY_DEVICE=cpu
RADIOLOGY_MODEL_CACHE_DIR=D:/ClaraMedCache/models
```

---

## Infrastructure Components

### 1. PostgreSQL 17

**Status:** ✓ Installed and Running  
**Service:** postgresql-x64-17  
**Database:** claramed  
**User:** claramed  

**Initial Setup Required:**

The PostgreSQL password must be reset before first use:

```powershell
# Run password reset script
.\scripts\reset_postgres_password.ps1
```

You will be prompted for the `postgres` superuser password. This script will:
1. Reset the `claramed` user password to `claramed`
2. Test the connection
3. Verify database access

**Manual Verification:**

```powershell
# Check service status
Get-Service postgresql-x64-17

# Test connection with Python
python -c "import psycopg2; conn = psycopg2.connect('postgresql://claramed:claramed@localhost:5432/claramed'); print('Connected'); conn.close()"
```

### 2. Redis 3.0.504

**Status:** ✓ Installed and Running  
**Service:** Redis  
**URL:** redis://localhost:6379/0  

**Note:** Uses RESP2 protocol for compatibility with Redis 3.x

**Verification:**

```powershell
# Check service status
Get-Service Redis

# Test with Python
python -c "import redis; r = redis.StrictRedis(host='localhost', port=6379, db=0, protocol=2); print('PING:', r.ping())"
```

### 3. Groq API

**Status:** ✓ Configured and Tested  
**Model:** openai/gpt-oss-120b  
**API Key:** Configured in `.env`  

**Verification:**

```powershell
python -c "from groq import Groq; import os; client = Groq(); response = client.chat.completions.create(messages=[{'role': 'user', 'content': 'test'}], model='openai/gpt-oss-120b'); print('OK:', response.choices[0].message.content)"
```

### 4. Tesseract OCR 5.4.0

**Status:** ✓ Installed and Tested  
**Path:** C:/Program Files/Tesseract-OCR/tesseract.exe  
**Languages:** English (eng)  

**Verification:**

```powershell
& "C:/Program Files/Tesseract-OCR/tesseract.exe" --version
```

### 5. PyTorch & TorchXRayVision

**Status:** ✓ Installed and Tested  
**PyTorch:** 2.15.0+cpu  
**TorchXRayVision:** 1.5.7  
**Model:** densenet121-res224-all  
**Cache:** D:/ClaraMedCache/models  

**Verification:**

```powershell
python -c "import torch; import torchxrayvision as xrv; print('PyTorch:', torch.__version__); print('TorchXRayVision:', xrv.__version__)"
```

### 6. Celery

**Status:** ✓ Configured  
**Broker:** Redis  
**Pool:** solo (Windows-compatible)  

**Verification:**

```powershell
# Test Celery configuration
python .\scripts\test_celery_task.py

# Start Celery worker manually
celery -A backend.workers.celery_app worker --pool=solo -l info
```

---

## Database Setup

### Initialize Database Schema

Once PostgreSQL password is reset, initialize the database:

```powershell
# Initialize database and apply migrations
python .\scripts\initialize_database.py
```

This script will:
1. Test database connection
2. Generate initial Alembic migration (if needed)
3. Apply migrations to create tables
4. Verify schema

### Expected Tables

After initialization:
- `medical_analyses`
- `uploaded_documents`
- `analysis_results`
- `radiology_findings`
- `integration_clients`
- `audit_events`
- `alembic_version`

### Manual Migration Commands

```powershell
# Check current migration revision
alembic current

# View migration history
alembic history

# Create new migration (after model changes)
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## Starting ClaraMed

### Automated Startup (Recommended)

```powershell
# Start all services with one command
.\start_claramed.ps1
```

This will open separate PowerShell windows for:
- **FastAPI Backend** (http://localhost:8000)
- **Streamlit Frontend** (http://localhost:8501)
- **Celery Worker** (background processing)

### Manual Startup

**Terminal 1 - FastAPI Backend:**
```powershell
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Streamlit Frontend:**
```powershell
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1
streamlit run app.py
```

**Terminal 3 - Celery Worker:**
```powershell
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1
celery -A backend.workers.celery_app worker --pool=solo -l info
```

### Access Points

- **Frontend UI:** http://localhost:8501
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/api/docs
- **Health Check:** http://localhost:8000/api/v1/health

---

## Testing

### Comprehensive Infrastructure Test

```powershell
# Run full infrastructure test suite
python .\scripts\test_infrastructure.py
```

This tests:
- Python environment
- Package imports
- Groq API connectivity
- Tesseract OCR
- Redis connectivity
- Celery configuration
- PyTorch & radiology model
- PostgreSQL connection
- Backend module imports

**Expected Output:** 8/9 tests pass (PostgreSQL requires password reset first)

### Individual Component Tests

```powershell
# Test database connection
python -c "import psycopg2; conn = psycopg2.connect('postgresql://claramed:claramed@localhost:5432/claramed'); print('OK'); conn.close()"

# Test Redis
python -c "import redis; r = redis.StrictRedis(host='localhost', port=6379, db=0, protocol=2); print(r.ping())"

# Test Groq API
python .\check_groq_models.py

# Test Tesseract OCR
python -c "import pytesseract; pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'; print(pytesseract.get_tesseract_version())"

# Test radiology model
python -c "import torchxrayvision as xrv; model = xrv.models.DenseNet(weights='densenet121-res224-all'); print('Model loaded')"
```

### Backend API Tests

```powershell
# Start backend first, then:

# Health check
curl http://localhost:8000/api/v1/health

# API documentation
# Open browser: http://localhost:8000/api/docs
```

---

## Troubleshooting

### PostgreSQL Connection Issues

**Symptom:** `password authentication failed for user "claramed"`

**Solution:**
```powershell
.\scripts\reset_postgres_password.ps1
```

### Redis Connection Issues

**Symptom:** `unknown command 'HELLO'`

**Solution:** This occurs with Redis 3.x. The application is configured to use RESP2 protocol automatically. Verify Redis service is running:

```powershell
Get-Service Redis
# If stopped:
Start-Service Redis
```

### Celery Worker Not Processing Tasks

**Verify:**
1. Redis is running
2. Celery worker is started with `--pool=solo`
3. Check worker logs for errors

```powershell
# Restart worker with verbose logging
celery -A backend.workers.celery_app worker --pool=solo -l debug
```

### Model Download Issues

**PyTorch models** are cached in: `D:\ClaraMedCache\models`

If download fails:
- Check internet connection
- Ensure D: drive has sufficient space
- Try manually downloading model weights

### Import Errors

**Verify virtual environment:**
```powershell
python -c "import sys; print(sys.executable)"
# Should show: D:\ClaraMedEnv\venv\Scripts\python.exe
```

**Reinstall dependencies if needed:**
```powershell
pip install -r requirements.txt
```

### Port Conflicts

If ports 8000 or 8501 are in use:

```powershell
# Find process using port
netstat -ano | findstr :8000
netstat -ano | findstr :8501

# Kill process (replace PID)
taskkill /PID <PID> /F
```

---

## Quick Reference Commands

```powershell
# Start everything
.\start_claramed.ps1

# Reset database password
.\scripts\reset_postgres_password.ps1

# Initialize database
python .\scripts\initialize_database.py

# Run infrastructure tests
python .\scripts\test_infrastructure.py

# Check services
Get-Service postgresql-x64-17, Redis

# Activate environment
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1
```

---

## System Specifications

- **OS:** Windows 11
- **RAM:** 8 GB
- **CPU:** 4 logical processors (Intel)
- **GPU:** Integrated graphics (CPU inference only)
- **Storage:** D: drive for caches and models

---

## Notes

1. **No Docker:** All services run natively on Windows
2. **CPU Inference:** PyTorch models run on CPU (no CUDA)
3. **Redis 3.x:** Uses RESP2 protocol for compatibility
4. **Celery Pool:** Uses `--pool=solo` for Windows compatibility
5. **Development Mode:** Running in development with debug enabled

---

## Support

For issues or questions:
1. Check logs in PowerShell windows
2. Run `python .\scripts\test_infrastructure.py`
3. Review error messages and check this troubleshooting guide
4. Verify all services are running with `Get-Service`
