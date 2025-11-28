# setup_local_db.ps1
# Sets up the local database for Slomix Discord (Postgres via Docker or SQLite)

$DestPath = "C:\Users\seareal\Documents\slomix_discord"
if (-not (Test-Path $DestPath)) {
    # If running from Z:, assume we are prepping for C:
    # But ideally this runs ON C: after migration.
    # Let's assume current dir if DestPath doesn't exist yet (or we are testing).
    $DestPath = Get-Location
}

Set-Location $DestPath

Write-Host "🗄️ Setting up Local Database..." -ForegroundColor Cyan

# 1. Check for Docker
$DockerAvailable = $false
try {
    docker --version | Out-Null
    $DockerAvailable = $true
    Write-Host "🐳 Docker is available." -ForegroundColor Green
} catch {
    Write-Host "⚠️ Docker not found." -ForegroundColor Yellow
}

# 2. Ask User Preference
$UsePostgres = $false
if ($DockerAvailable) {
    $Choice = Read-Host "Do you want to start a local PostgreSQL container? (Y/n)"
    if ($Choice -eq "" -or $Choice -match "^[Yy]") {
        $UsePostgres = $true
    }
} else {
    Write-Host "❌ Docker is missing. You cannot run Postgres easily without it." -ForegroundColor Red
    $Choice = Read-Host "Do you have a local Postgres installed manually? (y/N)"
    if ($Choice -match "^[Yy]") {
        $UsePostgres = $true
        Write-Host "ℹ️ Assuming local Postgres is running on port 5432." -ForegroundColor Yellow
    }
}

# 3. Configure .env
$EnvFile = Join-Path $DestPath ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $DestPath ".env.example") $EnvFile
}

$EnvContent = Get-Content $EnvFile

if ($UsePostgres) {
    Write-Host "🐘 Configuring for PostgreSQL..." -ForegroundColor Cyan
    
    if ($DockerAvailable) {
        # Start Docker Container
        $ContainerName = "slomix_postgres_local"
        $DbPassword = "local_secure_password"
        
        # Check if running
        $Running = docker ps -q -f name=$ContainerName
        if (-not $Running) {
             # Check if exists but stopped
             $Exists = docker ps -aq -f name=$ContainerName
             if ($Exists) {
                 Write-Host "🔄 Starting existing container..."
                 docker start $ContainerName
             } else {
                 Write-Host "🆕 Creating new Postgres container..."
                 docker run --name $ContainerName -e POSTGRES_PASSWORD=$DbPassword -e POSTGRES_DB=etlegacy -p 5432:5432 -d postgres:15
                 Start-Sleep -Seconds 5 # Wait for boot
             }
        }
    }

    # Update .env for Local Postgres
    $EnvContent = $EnvContent -replace "^DATABASE_TYPE=.*", "DATABASE_TYPE=postgresql"
    $EnvContent = $EnvContent -replace "^POSTGRES_HOST=.*", "POSTGRES_HOST=localhost"
    $EnvContent = $EnvContent -replace "^POSTGRES_PASSWORD=.*", "POSTGRES_PASSWORD=local_secure_password"
    
    # Find latest SQL dump to import
    $LatestDump = Get-ChildItem -Path $DestPath -Filter "postgresql_backup_*.sql" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    
    if ($LatestDump) {
        Write-Host "📥 Importing latest dump: $($LatestDump.Name)..." -ForegroundColor Cyan
        if ($DockerAvailable) {
            # Copy dump to container and import
            docker cp $LatestDump.FullName "$($ContainerName):/tmp/dump.sql"
            docker exec -i $ContainerName psql -U postgres -d etlegacy -f /tmp/dump.sql
        } else {
            Write-Host "⚠️ Manual Postgres detected. Please import '$($LatestDump.Name)' manually." -ForegroundColor Yellow
        }
    } else {
        Write-Host "⚠️ No SQL dump found to import." -ForegroundColor Yellow
    }

} else {
    Write-Host "📂 Configuring for SQLite (Fallback)..." -ForegroundColor Yellow
    $EnvContent = $EnvContent -replace "^DATABASE_TYPE=.*", "DATABASE_TYPE=sqlite"
    # SQLite usually doesn't need host/pass, but we leave them or comment them.
    # The adapter handles it.
}

$EnvContent | Set-Content $EnvFile
Write-Host "✅ .env updated." -ForegroundColor Green
Write-Host "🎉 Database Setup Complete!" -ForegroundColor Green
