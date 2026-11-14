# ClaraMed Quick Start Guide

## First Time Setup (One-Time Only)

### 1. Reset PostgreSQL Password

```powershell
.\scripts\reset_postgres_password.ps1
```

You'll be prompted for the `postgres` superuser password. This resets the `claramed` user password to match the configuration in `.env`.

### 2. Initialize Database

```powershell
python .\scripts\initialize_database.py
```

This will:
- Test database connection
- Generate Alembic migrations
- Create all database tables
- Verify schema

### 3. Verify Infrastructure

```powershell
python .\scripts\test_infrastructure.py
```

Expected result: **9/9 tests passed** ✓

---

## Starting ClaraMed

### Option 1: Automated (Recommended)

```powershell
.\start_claramed.ps1
```

This opens three PowerShell windows for:
- **FastAPI Backend** → http://localhost:8000
- **Streamlit Frontend** → http://localhost:8501
- **Celery Worker** → Background processing

### Option 2: Manual

**Terminal 1 - Activate Environment:**
```powershell
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1
```

**Terminal 2 - Start Backend:**
```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 3 - Start Frontend:**
```powershell
streamlit run app.py
```

**Terminal 4 - Start Worker (Optional):**
```powershell
celery -A backend.workers.celery_app worker --pool=solo -l info
```

---

## Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:8501 | Streamlit UI |
| Backend | http://localhost:8000 | FastAPI Server |
| API Docs | http://localhost:8000/api/docs | Interactive API |
| Health | http://localhost:8000/api/v1/health | Health Check |

---

## Stopping ClaraMed

Simply close the PowerShell windows where the services are running.

Or press `Ctrl+C` in each terminal if started manually.

---

## Troubleshooting

### PostgreSQL Connection Failed

```powershell
.\scripts\reset_postgres_password.ps1
```

### Check Services

```powershell
Get-Service postgresql-x64-17, Redis
```

Both should show "Running"

### Run Full Test Suite

```powershell
python .\scripts\test_infrastructure.py
```

### Check Python Environment

```powershell
python -c "import sys; print(sys.executable)"
```

Should show: `D:\ClaraMedEnv\venv\Scripts\python.exe`

---

## Common Commands

```powershell
# Activate environment
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1

# Check database status
python -c "import psycopg2; conn = psycopg2.connect('postgresql://claramed:claramed@localhost:5432/claramed'); print('Connected'); conn.close()"

# Check Redis
python -c "import redis; r = redis.StrictRedis(host='localhost', port=6379, db=0, protocol=2); print('Redis:', r.ping())"

# View Alembic history
alembic history

# Check current migration
alembic current
```

---

## File Locations

| Item | Location |
|------|----------|
| Project | `C:\Users\user\OneDrive\Desktop\claramed-main\claramed-main` |
| Virtual Environment | `D:\ClaraMedEnv\venv` |
| Model Cache | `D:\ClaraMedCache\models` |
| PostgreSQL | `C:\Program Files\PostgreSQL\17` |
| Tesseract OCR | `C:\Program Files\Tesseract-OCR` |
| Configuration | `.env` (project root) |

---

## Need Help?

1. **Setup Guide:** `docs/development/windows/SETUP_AND_VERIFICATION.md`
2. **Implementation Status:** `IMPLEMENTATION_STATUS.md`
3. **API Documentation:** `docs/API.md`
4. **Architecture:** `docs/ARCHITECTURE.md`

---

**Status:** Production-ready ✓  
**Last Updated:** November 11, 2026
