# migrate_to_laptop.ps1
# Migrates the Slomix Discord project from Z: drive to local C: drive

$SourcePath = "Z:\slomix_discord"
$DestPath = "C:\Users\seareal\Documents\slomix_discord"

Write-Host "🚀 Starting Migration from $SourcePath to $DestPath..." -ForegroundColor Cyan

# 1. Create Destination Directory
if (-not (Test-Path -Path $DestPath)) {
    Write-Host "📂 Creating destination directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $DestPath -Force | Out-Null
} else {
    Write-Host "📂 Destination directory already exists." -ForegroundColor Yellow
}

# 2. Copy Files (Robocopy is faster and handles exclusions better)
Write-Host "📦 Copying files (this may take a while)..." -ForegroundColor Cyan

# Robocopy arguments:
# /E - Copy subdirectories, including empty ones.
# /XO - Exclude older files (only copy new/changed).
# /XD - Exclude directories (venv, __pycache__, .git if you want a fresh start, but we keep git).
# /XF - Exclude files (*.pyc).
# /R:0 /W:0 - No retries on failure (fail fast).

$RoboArgs = @(
    $SourcePath,
    $DestPath,
    "/E",
    "/XO",
    "/XD", ".venv", "__pycache__", "node_modules", ".vscode",
    "/XF", "*.pyc", "*.log",
    "/R:0", "/W:0"
)

# Run Robocopy
& robocopy @RoboArgs

# Robocopy exit codes: 0-7 are success/partial success. 8+ are failures.
if ($LASTEXITCODE -ge 8) {
    Write-Host "❌ Robocopy failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Files copied successfully!" -ForegroundColor Green

# 3. Setup Virtual Environment
$VenvPath = Join-Path $DestPath ".venv"

if (-not (Test-Path -Path $VenvPath)) {
    Write-Host "🐍 Creating Python virtual environment..." -ForegroundColor Cyan
    Set-Location -Path $DestPath
    python -m venv .venv
    Write-Host "✅ Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "🐍 Virtual environment already exists." -ForegroundColor Yellow
}

# 4. Install Dependencies
Write-Host "⬇️ Installing dependencies..." -ForegroundColor Cyan
$PipPath = Join-Path $VenvPath "Scripts\python.exe"
& $PipPath -m pip install -r (Join-Path $DestPath "requirements.txt")

Write-Host "🎉 Migration Complete!" -ForegroundColor Green
Write-Host "👉 Go to: $DestPath"
Write-Host "👉 Run: .\setup_local_db.ps1 (to setup database)"
