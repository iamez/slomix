# Quick PostgreSQL Setup for ET:Legacy Bot
$psqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL Setup for ET:Legacy Bot" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Test connection
Write-Host "Testing PostgreSQL connection..." -ForegroundColor Yellow
Write-Host "You will be prompted for the 'postgres' user password you set during installation." -ForegroundColor White
Write-Host ""

# Set password
$password = Read-Host "Enter postgres password" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
$env:PGPASSWORD = $plainPassword

Write-Host ""
Write-Host "Creating database and user..." -ForegroundColor Yellow

# Create SQL commands file
$sqlFile = Join-Path $PSScriptRoot "setup_temp.sql"
@"
CREATE DATABASE etlegacy;
CREATE USER etlegacy_user WITH PASSWORD 'etlegacy_secure_2025';
GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etlegacy_user;
\c etlegacy
GRANT ALL ON SCHEMA public TO etlegacy_user;
"@ | Out-File -FilePath $sqlFile -Encoding UTF8

# Run SQL commands
try {
    & $psqlPath -U postgres -h localhost -f $sqlFile
    Write-Host ""
    Write-Host "✅ Database 'etlegacy' created!" -ForegroundColor Green
    Write-Host "✅ User 'etlegacy_user' created!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Database credentials:" -ForegroundColor Cyan
    Write-Host "  Host: localhost" -ForegroundColor White
    Write-Host "  Port: 5432" -ForegroundColor White
    Write-Host "  Database: etlegacy" -ForegroundColor White
    Write-Host "  User: etlegacy_user" -ForegroundColor White
    Write-Host "  Password: etlegacy_secure_2025" -ForegroundColor White
    Write-Host ""
    Write-Host "Applying schema..." -ForegroundColor Yellow
    
    $env:PGPASSWORD = "etlegacy_secure_2025"
    $schemaFile = Join-Path $PSScriptRoot "tools\schema_postgresql.sql"
    & $psqlPath -U etlegacy_user -h localhost -d etlegacy -f $schemaFile
    
    Write-Host ""
    Write-Host "✅ Schema applied successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next step: Run the migration script to copy your data" -ForegroundColor Yellow
    Write-Host "  python tools/migrate_to_postgresql.py" -ForegroundColor White
} catch {
    Write-Host ""
    Write-Host "❌ Error: $_" -ForegroundColor Red
} finally {
    # Clean up
    Remove-Item $sqlFile -ErrorAction SilentlyContinue
}
