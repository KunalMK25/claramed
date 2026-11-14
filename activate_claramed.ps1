# ClaraMed Environment Activation Script
# Run this before working on ClaraMed: .\activate_claramed.ps1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   ClaraMed Environment Activation" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& D:\ClaraMedEnv\venv\Scripts\Activate.ps1

# Set cache directories to D: drive
Write-Host "Setting cache directories to D: drive..." -ForegroundColor Yellow
$env:PIP_CACHE_DIR = "D:\ClaraMedCache\pip"
$env:TEMP = "D:\ClaraMedTemp"
$env:TMP = "D:\ClaraMedTemp"
$env:TORCH_HOME = "D:\ClaraMedCache\models"
$env:XDG_CACHE_HOME = "D:\ClaraMedCache\models"

# Navigate to project directory
Write-Host "Navigating to project directory..." -ForegroundColor Yellow
Set-Location "c:\Users\user\OneDrive\Desktop\claramed-main\claramed-main"

# Display environment info
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   Environment Ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

$pythonVersion = & python --version 2>&1
Write-Host "✅ Python: $pythonVersion" -ForegroundColor Cyan
Write-Host "✅ Virtual Env: $env:VIRTUAL_ENV" -ForegroundColor Cyan
Write-Host "✅ Model Cache: $env:TORCH_HOME" -ForegroundColor Cyan
Write-Host "✅ Project: $(Get-Location)" -ForegroundColor Cyan

Write-Host "`nQuick commands:" -ForegroundColor Yellow
Write-Host "  python validate_setup.py       - Run environment validation" -ForegroundColor Gray
Write-Host "  uvicorn app:app --reload       - Start FastAPI backend" -ForegroundColor Gray
Write-Host "  streamlit run app.py           - Start Streamlit frontend" -ForegroundColor Gray
Write-Host "  alembic upgrade head           - Run database migrations" -ForegroundColor Gray
Write-Host "  python -m pip list             - List installed packages" -ForegroundColor Gray
Write-Host "  python -m pip check            - Check for conflicts`n" -ForegroundColor Gray
