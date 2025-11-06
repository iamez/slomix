# Clean GitHub Repository - Keep Only Essential Files
# This script removes all unnecessary files and keeps only production-ready code

Write-Host "`n🧹 GITHUB CLEANUP SCRIPT" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

# Create a list of files to KEEP
$filesToKeep = @(
    # Core bot files
    "bot/__init__.py",
    "bot/ultimate_bot.py",
    "bot/community_stats_parser.py",
    "bot/config.py",
    "bot/logging_config.py",
    
    # Bot cogs
    "bot/cogs/__init__.py",
    "bot/cogs/admin_cog.py",
    "bot/cogs/last_session_cog.py",
    "bot/cogs/leaderboard_cog.py",
    "bot/cogs/link_cog.py",
    "bot/cogs/session_cog.py",
    "bot/cogs/stats_cog.py",
    "bot/cogs/sync_cog.py",
    
    # Bot core modules
    "bot/core/__init__.py",
    "bot/core/database_adapter.py",
    "bot/core/stats_cache.py",
    "bot/core/achievement_system.py",
    
    # Database manager
    "postgresql_database_manager.py",
    
    # Configuration
    ".env.example",
    ".gitignore",
    "requirements.txt",
    
    # Documentation - Essential only
    "README.md",
    "LICENSE",
    "SAFETY_VALIDATION_SYSTEMS.md",
    "ROUND_2_PIPELINE_EXPLAINED.txt",
    "AUTOMATION_SETUP_GUIDE.md",
    "DISASTER_RECOVERY.md",
    
    # Deployment scripts
    "setup_linux_bot.sh",
    "setup_postgres_simple.ps1"
)

# Get all currently tracked files
$allFiles = git ls-files

# Find files to remove (all tracked files NOT in the keep list)
$filesToRemove = $allFiles | Where-Object {
    $file = $_
    $keep = $false
    foreach ($keepFile in $filesToKeep) {
        if ($file -eq $keepFile) {
            $keep = $true
            break
        }
    }
    -not $keep
}

Write-Host "📊 Statistics:" -ForegroundColor Yellow
Write-Host "  Total tracked files: $($allFiles.Count)" -ForegroundColor White
Write-Host "  Files to keep: $($filesToKeep.Count)" -ForegroundColor Green
Write-Host "  Files to remove: $($filesToRemove.Count)" -ForegroundColor Red
Write-Host ""

# Show confirmation
Write-Host "⚠️  WARNING: This will remove $($filesToRemove.Count) files from git tracking!" -ForegroundColor Red
Write-Host "   (Files will still exist locally, just not tracked by git)`n" -ForegroundColor Yellow

$confirmation = Read-Host "Type 'YES DELETE' to proceed"

if ($confirmation -ne "YES DELETE") {
    Write-Host "`n❌ Cancelled. No changes made." -ForegroundColor Red
    exit
}

Write-Host "`n🗑️  Removing files from git..." -ForegroundColor Cyan

# Remove files from git tracking
$count = 0
foreach ($file in $filesToRemove) {
    try {
        git rm --cached $file 2>$null
        $count++
        if ($count % 50 -eq 0) {
            Write-Host "  Removed $count files..." -ForegroundColor Gray
        }
    }
    catch {
        # Ignore errors (file might already be removed)
    }
}

Write-Host "`n✅ Removed $count files from git tracking" -ForegroundColor Green

# Update .gitignore to ignore removed files
Write-Host "`n📝 Updating .gitignore..." -ForegroundColor Cyan

$gitignoreContent = @"
# Database files
*.db
*.db-*
*.sqlite
*.sqlite3

# Backup files
*.backup
*.bak
*.old

# Logs
logs/
*.log

# Environment files
.env
config.json
bot_config.json
bot/config.json

# Local stats files
local_stats/
bot/local_stats/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Test files
test_*.py
*_test.py
check_*.py
quick_*.py
analyze_*.py

# Archive/backup directories
archive/
backups/
backup/
database_backups/

# Documentation we don't need on GitHub
docs/archive/
dev/
tools/
scripts/
analytics/

# Temporary files
*.tmp
*.temp
*.zip
*.png
*.jpg
"@

Set-Content -Path ".gitignore" -Value $gitignoreContent

Write-Host "✅ Updated .gitignore" -ForegroundColor Green

# Show what's left
Write-Host "`n📦 Files remaining in git:" -ForegroundColor Cyan
$remaining = git ls-files
$remaining | Sort-Object | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host "`n📊 Final Statistics:" -ForegroundColor Yellow
Write-Host "  Files tracked: $($remaining.Count)" -ForegroundColor Green
Write-Host ""

Write-Host "✅ Cleanup complete!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  1. Review changes: git status" -ForegroundColor White
Write-Host "  2. Commit: git commit -m 'Clean up repository - keep only essential files'" -ForegroundColor White
Write-Host "  3. Push: git push origin vps-network-migration" -ForegroundColor White
Write-Host ""
