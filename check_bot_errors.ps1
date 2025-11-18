# Quick Error Log Viewer
# Shows only ERROR and WARNING level logs from bot

param(
    [int]$Lines = 100
)

Write-Host "🔍 Checking bot logs for errors..." -ForegroundColor Cyan
Write-Host ""

$logFile = "logs/bot.log"

if (!(Test-Path $logFile)) {
    Write-Host "❌ Log file not found: $logFile" -ForegroundColor Red
    exit 1
}

# Get file size
$fileSize = (Get-Item $logFile).Length / 1MB
Write-Host "📊 Log file size: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Gray
Write-Host ""

# Extract ERROR and WARNING lines
Write-Host "🚨 ERRORS:" -ForegroundColor Red
Get-Content $logFile -Tail $Lines | Select-String -Pattern " ERROR " | ForEach-Object {
    Write-Host $_ -ForegroundColor Red
}

Write-Host ""
Write-Host "⚠️  WARNINGS:" -ForegroundColor Yellow
Get-Content $logFile -Tail $Lines | Select-String -Pattern " WARNING " | ForEach-Object {
    Write-Host $_ -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Done! Checked last $Lines lines" -ForegroundColor Green
