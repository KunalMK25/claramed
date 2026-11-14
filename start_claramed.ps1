# ClaraMed Complete Startup Script
# Starts all required services for ClaraMed

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "              ClaraMed Startup Script" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Check if running from correct directory
if (!(Test-Path ".\backend\main.py")) {
    Write-Host "Error: Please run this script from the ClaraMed project root directory" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "1. Checking Python virtual environment..." -ForegroundColor Yellow
if (Test-Path "D:\ClaraMedEnv\venv\Scripts\Activate.ps1") {
    & "D:\ClaraMedEnv\venv\Scripts\Activate.ps1"
    Write-Host "   ✓ Virtual environment activated`n" -ForegroundColor Green
} else {
    Write-Host "   ✗ Virtual environment not found at D:\ClaraMedEnv\venv" -ForegroundColor Red
    exit 1
}

# Check PostgreSQL service
Write-Host "2. Checking PostgreSQL service..." -ForegroundColor Yellow
$pgService = Get-Service -Name "postgresql-x64-17" -ErrorAction SilentlyContinue
if ($pgService -and $pgService.Status -eq "Running") {
    Write-Host "   ✓ PostgreSQL is running`n" -ForegroundColor Green
} else {
    Write-Host "   ✗ PostgreSQL service not running" -ForegroundColor Red
    Write-Host "   Starting PostgreSQL..." -ForegroundColor Yellow
    Start-Service -Name "postgresql-x64-17" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "   ✓ PostgreSQL started`n" -ForegroundColor Green
}

# Check Redis service
Write-Host "3. Checking Redis service..." -ForegroundColor Yellow
$redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
if ($redisService -and $redisService.Status -eq "Running") {
    Write-Host "   ✓ Redis is running`n" -ForegroundColor Green
} else {
    Write-Host "   ⚠ Redis service not running" -ForegroundColor Yellow
    Write-Host "   Attempting to start Redis..." -ForegroundColor Yellow
    Start-Service -Name "Redis" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
    if ($redisService -and $redisService.Status -eq "Running") {
        Write-Host "   ✓ Redis started`n" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ Could not start Redis automatically" -ForegroundColor Yellow
        Write-Host "   Celery workers may not function properly`n" -ForegroundColor Yellow
    }
}

# Test database connection
Write-Host "4. Testing database connection..." -ForegroundColor Yellow
D:\ClaraMedEnv\venv\Scripts\python.exe -c "import psycopg2; conn = psycopg2.connect('postgresql://claramed:claramed@localhost:5432/claramed'); print('   ✓ Database connection successful'); conn.close()" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ✗ Database connection failed" -ForegroundColor Red
    Write-Host "   Please run: .\scripts\reset_postgres_password.ps1`n" -ForegroundColor Yellow
} else {
    Write-Host ""
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "              Starting ClaraMed Services" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

Write-Host "Starting services in separate windows...`n" -ForegroundColor Yellow

# Start FastAPI backend
Write-Host "→ FastAPI Backend: http://localhost:8000" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; D:\ClaraMedEnv\venv\Scripts\Activate.ps1; Write-Host 'Starting FastAPI Backend...' -ForegroundColor Green; D:\ClaraMedEnv\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 2

# Start Streamlit frontend
Write-Host "→ Streamlit Frontend: http://localhost:8501" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; D:\ClaraMedEnv\venv\Scripts\Activate.ps1; Write-Host 'Starting Streamlit Frontend...' -ForegroundColor Green; D:\ClaraMedEnv\venv\Scripts\streamlit.exe run app.py"

Start-Sleep -Seconds 2

# Start Celery worker
Write-Host "→ Celery Worker: Background task processing" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; D:\ClaraMedEnv\venv\Scripts\Activate.ps1; Write-Host 'Starting Celery Worker...' -ForegroundColor Green; D:\ClaraMedEnv\venv\Scripts\celery.exe -A backend.workers.celery_app worker --pool=solo -l info"

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "              ClaraMed Started Successfully" -ForegroundColor Green
Write-Host "============================================================`n" -ForegroundColor Cyan

Write-Host "Access the application at:" -ForegroundColor Yellow
Write-Host "  • Frontend:  http://localhost:8501" -ForegroundColor Cyan
Write-Host "  • Backend:   http://localhost:8000" -ForegroundColor Cyan
Write-Host "  • API Docs:  http://localhost:8000/api/docs" -ForegroundColor Cyan

Write-Host "`nPress Ctrl+C to stop this script (services will continue running)" -ForegroundColor Gray
Write-Host "To stop services, close their PowerShell windows`n" -ForegroundColor Gray

# Keep script running
while ($true) {
    Start-Sleep -Seconds 10
}
