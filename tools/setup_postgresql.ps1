# PostgreSQL Installation & Setup Script for Windows
# Run this AFTER installing PostgreSQL manually

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL Setup Helper for ET:Legacy Bot" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if PostgreSQL is installed
Write-Host "Step 1: Checking PostgreSQL installation..." -ForegroundColor Yellow
try {
    $version = psql --version
    Write-Host "✅ PostgreSQL is installed: $version" -ForegroundColor Green
} catch {
    Write-Host "❌ PostgreSQL not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install PostgreSQL first:" -ForegroundColor Yellow
    Write-Host "1. Download from: https://www.postgresql.org/download/windows/" -ForegroundColor White
    Write-Host "2. Run the installer" -ForegroundColor White
    Write-Host "3. Remember the postgres user password!" -ForegroundColor White
    Write-Host "4. Re-run this script after installation" -ForegroundColor White
    exit
}

Write-Host ""
Write-Host "Step 2: Getting database password..." -ForegroundColor Yellow
$password = Read-Host "Enter the password you set for 'postgres' user during installation" -AsSecureString
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

Write-Host ""
Write-Host "Step 3: Creating database and user..." -ForegroundColor Yellow

# Create database and user
$env:PGPASSWORD = $plainPassword

$commands = @"
CREATE DATABASE etlegacy;
CREATE USER etlegacy_user WITH PASSWORD 'etlegacy_secure_2025';
GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etlegacy_user;
\c etlegacy
GRANT ALL ON SCHEMA public TO etlegacy_user;
"@

try {
    $commands | psql -U postgres -h localhost
    Write-Host "✅ Database 'etlegacy' created" -ForegroundColor Green
    Write-Host "✅ User 'etlegacy_user' created" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to create database: $_" -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "Step 4: Applying schema..." -ForegroundColor Yellow
try {
    $env:PGPASSWORD = "etlegacy_secure_2025"
    psql -U etlegacy_user -d etlegacy -h localhost -f tools/schema_postgresql.sql
    Write-Host "✅ Schema applied successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to apply schema: $_" -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "Step 5: Updating config.json..." -ForegroundColor Yellow

$configPath = "config.json"
if (Test-Path $configPath) {
    $config = Get-Content $configPath | ConvertFrom-Json
    
    # Add PostgreSQL config if not present
    if (-not $config.postgresql_host) {
        $config | Add-Member -NotePropertyName "postgresql_host" -NotePropertyValue "localhost" -Force
        $config | Add-Member -NotePropertyName "postgresql_port" -NotePropertyValue 5432 -Force
        $config | Add-Member -NotePropertyName "postgresql_database" -NotePropertyValue "etlegacy" -Force
        $config | Add-Member -NotePropertyName "postgresql_user" -NotePropertyValue "etlegacy_user" -Force
        $config | Add-Member -NotePropertyName "postgresql_password" -NotePropertyValue "etlegacy_secure_2025" -Force
        
        $config | ConvertTo-Json -Depth 10 | Set-Content $configPath
        Write-Host "✅ PostgreSQL config added to config.json" -ForegroundColor Green
        Write-Host "   (database_type still set to 'sqlite')" -ForegroundColor Yellow
    } else {
        Write-Host "✅ PostgreSQL config already exists in config.json" -ForegroundColor Green
    }
} else {
    Write-Host "⚠️  config.json not found - please update manually" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "✅ PostgreSQL Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Run migration: python tools/migrate_to_postgresql.py" -ForegroundColor White
Write-Host "2. Update config.json: database_type = 'postgresql'" -ForegroundColor White
Write-Host "3. Restart bot: .\restart_bot.bat" -ForegroundColor White
Write-Host "4. Test all commands!" -ForegroundColor White
Write-Host ""

Remove-Item Env:\PGPASSWORD
