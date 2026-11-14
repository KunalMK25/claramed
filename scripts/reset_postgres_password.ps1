# Reset PostgreSQL claramed user password
# Run this script and enter the postgres superuser password when prompted

Write-Host "Resetting PostgreSQL 'claramed' user password to 'claramed'" -ForegroundColor Cyan
Write-Host "You will be prompted for the postgres superuser password..." -ForegroundColor Yellow
Write-Host ""

& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "ALTER USER claramed WITH PASSWORD 'claramed';"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Password reset successfully!" -ForegroundColor Green
    Write-Host "Testing connection..." -ForegroundColor Cyan
    
    $env:PGPASSWORD = "claramed"
    & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U claramed -d claramed -c "SELECT current_user, current_database();"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Connection test successful!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Connection test failed. Please check the configuration." -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "Password reset failed. Please verify the postgres password." -ForegroundColor Red
}
