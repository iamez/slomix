#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Complete database rebuild process
.DESCRIPTION
    Runs all steps of database rebuild with validation
#>

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "Database Rebuild Process" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Gray

# Set UTF-8 encoding
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Step 1: Validate current state
Write-Host "`n[STEP 1] Current State" -ForegroundColor Yellow
python validate_schema.py

$continue = Read-Host "`nContinue with rebuild? (y/N)"
if ($continue -ne 'y' -and $continue -ne 'Y') {
    Write-Host "[CANCEL] Rebuild cancelled" -ForegroundColor Red
    exit
}

# Step 2: Clear database
Write-Host "`n[STEP 2] Clearing database..." -ForegroundColor Yellow
python tools/full_database_rebuild.py

# Step 3: Create fresh schema
Write-Host "`n[STEP 3] Creating fresh schema..." -ForegroundColor Yellow
python tools/create_fresh_database.py

# Step 4: Validate schema
Write-Host "`n[STEP 4] Validating schema..." -ForegroundColor Yellow
python validate_schema.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Schema validation failed! Fix issues before import." -ForegroundColor Red
    exit 1
}

# Step 5: Import
$import = Read-Host "`nProceed with import? (y/N)"
if ($import -ne 'y' -and $import -ne 'Y') {
    Write-Host "[SKIP] Import skipped. Run import_stats.ps1 when ready." -ForegroundColor Yellow
    exit
}

Write-Host "`n[STEP 5] Importing stats..." -ForegroundColor Yellow
python tools/simple_bulk_import.py | Select-Object -Last 100

# Step 6: Verify
Write-Host "`n[STEP 6] Verifying results..." -ForegroundColor Yellow
python check_duplicates.py

Write-Host "`n" + ("=" * 70) -ForegroundColor Gray
Write-Host "[DONE] Database rebuild complete!" -ForegroundColor Green
