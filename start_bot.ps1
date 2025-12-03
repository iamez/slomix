#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start the ET:Legacy Discord bot
.DESCRIPTION
    Starts the bot with proper UTF-8 encoding and error handling
#>

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "Starting ET:Legacy Discord Bot" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Gray

# Set UTF-8 encoding
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Check database exists
if (-not (Test-Path "etlegacy_production.db")) {
    Write-Host "[ERROR] Database not found! Run rebuild_database.ps1 first." -ForegroundColor Red
    exit 1
}

# Check .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] .env file not found! Bot token required." -ForegroundColor Red
    exit 1
}

Write-Host "[DB] Database: etlegacy_production.db" -ForegroundColor Green
Write-Host "[TOKEN] Loaded from .env" -ForegroundColor Green

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "[VENV] Activating virtual environment..." -ForegroundColor Green
    & .venv\Scripts\Activate.ps1
} else {
    Write-Host "[WARNING] Virtual environment not found - using system Python" -ForegroundColor Yellow
}

Write-Host "`n[START] Starting bot...`n" -ForegroundColor Yellow
Write-Host "=" * 70 -ForegroundColor Gray

# Run bot
try {
    python bot/ultimate_bot.py
}
catch {
    Write-Host "`n[CRASH] Bot crashed: $_" -ForegroundColor Red
}
finally {
    Write-Host "`n[STOP] Bot stopped" -ForegroundColor Yellow
}
