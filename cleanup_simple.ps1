# Clean GitHub Repository - Keep Only Essential Files
Write-Host "`nGITHUB CLEANUP SCRIPT" -ForegroundColor Cyan
Write-Host "========================`n" -ForegroundColor Cyan

# Files to KEEP (only production essentials)
$keepFiles = @"
bot/__init__.py
bot/ultimate_bot.py
bot/community_stats_parser.py
bot/config.py
bot/logging_config.py
bot/cogs/__init__.py
bot/cogs/admin_cog.py
bot/cogs/last_session_cog.py
bot/cogs/leaderboard_cog.py
bot/cogs/link_cog.py
bot/cogs/session_cog.py
bot/cogs/stats_cog.py
bot/cogs/sync_cog.py
bot/core/__init__.py
bot/core/database_adapter.py
bot/core/stats_cache.py
bot/core/achievement_system.py
postgresql_database_manager.py
.env.example
.gitignore
requirements.txt
README.md
LICENSE
SAFETY_VALIDATION_SYSTEMS.md
ROUND_2_PIPELINE_EXPLAINED.txt
AUTOMATION_SETUP_GUIDE.md
DISASTER_RECOVERY.md
setup_linux_bot.sh
setup_postgres_simple.ps1
"@

$filesToKeep = $keepFiles -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }

# Get all tracked files and find what to remove
$allFiles = git ls-files
$filesToRemove = @()

foreach ($file in $allFiles) {
    if ($file -notin $filesToKeep) {
        $filesToRemove += $file
    }
}

Write-Host "Statistics:" -ForegroundColor Yellow
Write-Host "  Total tracked files: $($allFiles.Count)"
Write-Host "  Files to keep: $($filesToKeep.Count)" -ForegroundColor Green
Write-Host "  Files to remove: $($filesToRemove.Count)" -ForegroundColor Red
Write-Host ""

Write-Host "WARNING: This will remove $($filesToRemove.Count) files from git!" -ForegroundColor Red
$confirm = Read-Host "Type YES to proceed"

if ($confirm -ne "YES") {
    Write-Host "Cancelled." -ForegroundColor Red
    exit
}

Write-Host "`nRemoving files..." -ForegroundColor Cyan
$count = 0
foreach ($file in $filesToRemove) {
    git rm --cached $file 2>$null | Out-Null
    $count++
    if ($count % 100 -eq 0) {
        Write-Host "  Removed $count files..."
    }
}

Write-Host "`nRemoved $count files from git" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  1. git status"
Write-Host "  2. git add -A"
Write-Host "  3. git commit -m 'Clean up repository - keep only essential files'"
Write-Host "  4. git push origin vps-network-migration`n"
