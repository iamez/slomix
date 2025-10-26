#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Validate database schema before import
.DESCRIPTION
    Runs schema validation with proper UTF-8 encoding
#>

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "Database Schema Validation" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Gray

# Set UTF-8 encoding
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Run validation
python validate_schema.py

# Check exit code
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[OK] Ready to proceed with import!" -ForegroundColor Green
} else {
    Write-Host "`n[WARNING] Fix schema issues before importing!" -ForegroundColor Yellow
}
