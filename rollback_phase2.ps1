# PHASE 2 ROLLBACK SCRIPT
# This script restores the database to pre-Phase 2 state

Write-Host "🔄 ROLLING BACK PHASE 2..." -ForegroundColor Yellow
Write-Host "=" * 60

# 1. Restore database backup
Write-Host "1. Restoring database backup..."
Copy-Item "bot/BACKUP_ROLLBACK.db" "bot/etlegacy_production.db" -Force
Write-Host "   ✅ Database restored" -ForegroundColor Green

# 2. Checkout git branch
Write-Host "2. Reverting git changes..."
git checkout team-system
git branch -D phase2-terminology-rename
Write-Host "   ✅ Git reverted to team-system branch" -ForegroundColor Green

Write-Host ""
Write-Host "=" * 60
Write-Host "✅ ROLLBACK COMPLETE - Pre-Phase 2 state restored" -ForegroundColor Green
Write-Host "=" * 60
