#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Bulk import stats files with proper UTF-8 encoding
.DESCRIPTION
    Wrapper script that ensures UTF-8 encoding and provides clean output
.PARAMETER Pattern
    File pattern to import (default: all .txt files in local_stats/)
.PARAMETER ShowLast
    Number of last lines to show (default: 100)
.EXAMPLE
    .\import_stats.ps1
    .\import_stats.ps1 -Pattern "local_stats/2025-10-*.txt"
    .\import_stats.ps1 -ShowLast 50
#>

param(
    [string]$Pattern = "",
    [int]$ShowLast = 100
)

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "ET:Legacy Stats Bulk Import" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Gray

# Set UTF-8 encoding
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Build command arguments safely
$arguments = @('tools/simple_bulk_import.py')
if ($Pattern) {
    Write-Host "[FILES] Pattern: $Pattern" -ForegroundColor Yellow
    $arguments += $Pattern
} else {
    Write-Host "[FILES] Importing all files from local_stats/" -ForegroundColor Yellow
}

Write-Host "[START] Starting import...`n" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Gray

# Run import and capture output (safely without Invoke-Expression)
$startTime = Get-Date
$output = & python $arguments 2>&1

# Show last N lines
$output | Select-Object -Last $ShowLast

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host "`n" + ("=" * 70) -ForegroundColor Gray
Write-Host "[TIME] Duration: $($duration.ToString('mm\:ss'))" -ForegroundColor Cyan
Write-Host "[DONE] Import complete!" -ForegroundColor Green
