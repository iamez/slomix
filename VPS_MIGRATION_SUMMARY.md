# 🚀 VPS Migration - Quick Summary

## What We're Doing
Moving from **local PC + SQLite** to **multi-VPS + PostgreSQL**

## Why?
- ✅ Bot runs 24/7 (no more PC downtime)
- ✅ Database always accessible
- ✅ Better performance and scalability
- ✅ Professional infrastructure
- ✅ Dev environments can test against real data

## What Changes?

### Code Changes Required
| File | Lines | Complexity | Changes Needed |
|------|-------|-----------|----------------|
| `bot/ultimate_bot.py` | ~4000 | 🔴 HIGH | Replace `aiosqlite` with `asyncpg`, update 10+ connections, change all `?` to `$1` |
| `database_manager.py` | ~1100 | 🔴 HIGH | Update import logic, schema creation, SQL syntax |
| `bot/cogs/last_session_cog.py` | ~2200 | 🟡 MEDIUM | Update 1 connection, query syntax |
| `bot/core/team_history.py` | ~500 | 🟡 MEDIUM | Replace `sqlite3` with `asyncpg` |
| `bot/schema.sql` | ~200 | 🔴 HIGH | Convert SQLite DDL to PostgreSQL DDL |
| `requirements.txt` | 13 | 🟢 LOW | Add `asyncpg`, remove `aiosqlite` |
| `.env` / `.env.example` | 76 | 🟢 LOW | Add PostgreSQL connection vars |

### Infrastructure Required
- **VPS 1 (Database)**: 4GB RAM, 50GB SSD, Ubuntu 22.04
- **VPS 2 (Bot)**: 2GB RAM, 20GB SSD, Ubuntu 22.04
- **Monthly cost**: ~$20-30 USD (DigitalOcean, Linode, Vultr)

## Key Technical Decisions Needed

### 1. Database Library: Raw SQL vs ORM?
**Option A: Raw SQL with asyncpg** (RECOMMENDED)
- ✅ Fastest performance
- ✅ You already write raw SQL
- ✅ Minimal learning curve
- ❌ Manual query building

**Option B: ORM with SQLAlchemy**
- ✅ Database-agnostic (easy to switch)
- ✅ Type safety
- ❌ Slower performance
- ❌ Learning curve
- ❌ More code to rewrite

**Recommendation**: Stick with raw SQL + asyncpg. You're already comfortable with SQL.

### 2. Dual Support: SQLite (dev) + PostgreSQL (prod)?
**Option A: PostgreSQL only**
- ✅ Simpler code
- ✅ Dev environment matches prod
- ❌ Need VPS access for local dev

**Option B: Support both (environment variable switch)**
- ✅ Can develop offline
- ✅ Easier testing
- ❌ More complex code
- ❌ Two code paths to maintain

**Recommendation**: PostgreSQL only. Set up read-only dev credentials.

### 3. Migration Downtime: How long is acceptable?
- **Minimum**: 1 hour (best case)
- **Realistic**: 2-3 hours (testing, verification)
- **Worst case**: 6 hours (if issues found)

**Recommendation**: Schedule during low-usage time (3am-6am), announce 48h in advance.

## Migration Strategy

### Phase 1: Preparation (1 week)
- [ ] Set up VPS 1 (PostgreSQL server)
- [ ] Set up VPS 2 (Bot server)
- [ ] Create `bot/core/database.py` abstraction layer
- [ ] Update `bot/ultimate_bot.py` connection logic
- [ ] Update all SQL queries (? → $1, $2, $3)
- [ ] Convert `bot/schema.sql` to PostgreSQL
- [ ] Test with empty PostgreSQL database

### Phase 2: Testing (3 days)
- [ ] Copy production SQLite to test database
- [ ] Migrate test data to PostgreSQL
- [ ] Run bot against PostgreSQL test database
- [ ] Verify all commands work
- [ ] Load test (simulate high traffic)
- [ ] Fix any issues found

### Phase 3: Migration Day (2-3 hours)
1. **T-0:00**: Announce bot going offline
2. **T+0:05**: Stop bot on local PC
3. **T+0:10**: Export SQLite data to SQL dump
4. **T+0:30**: Import data to PostgreSQL (verify checksums)
5. **T+1:00**: Deploy bot to VPS 2
6. **T+1:10**: Start bot, test basic commands
7. **T+1:30**: Monitor for errors
8. **T+2:00**: Announce bot back online
9. **T+3:00**: Final verification, declare success

### Phase 4: Monitoring (1 week)
- [ ] Daily checks for errors
- [ ] Performance monitoring
- [ ] Backup verification
- [ ] User feedback

## Rollback Plan

If migration fails at any point:

**Before data import (T+0:00 to T+0:30)**:
- Abort migration
- Start bot on local PC with SQLite
- Announce delay

**After data import (T+0:30 to T+2:00)**:
- Keep PostgreSQL database
- Run bot locally, point to PostgreSQL on VPS
- Debug and retry tomorrow

**Critical failure (data corruption)**:
- Restore SQLite from backup
- Start bot locally
- Schedule new migration date

## Cost Estimate

### VPS Hosting (monthly)
- **DigitalOcean**: $12/month (4GB) + $6/month (2GB) = **$18/month**
- **Linode**: $12/month (4GB) + $5/month (2GB) = **$17/month**
- **Vultr**: $12/month (4GB) + $6/month (2GB) = **$18/month**

### Time Investment
- **Setup & coding**: 20-30 hours
- **Testing**: 10 hours
- **Migration**: 3 hours
- **Documentation**: 5 hours
- **Total**: ~40 hours

### ROI
- ✅ 24/7 uptime (worth it for active community)
- ✅ Professional infrastructure
- ✅ Learning experience (DevOps skills)
- ✅ Scalability for future features

## Next Steps

1. **Review VPS_MIGRATION_PROMPT.md** (full technical details)
2. **Choose VPS provider** (DigitalOcean, Linode, Vultr)
3. **Create branch**: `git checkout -b remote-infrastructure`
4. **Start with abstraction layer**: `bot/core/database.py`
5. **Update one file at a time**, test thoroughly
6. **Schedule migration date** when ready

## Questions to Answer Before Starting

1. **Budget**: Is $18-20/month acceptable for VPS hosting?
2. **Downtime**: When is the best time for 2-3 hour maintenance?
3. **Access**: Who needs SSH access to VPS servers?
4. **Backups**: How often? (Daily recommended)
5. **Monitoring**: What tools? (UptimeRobot, Better Uptime, etc.)
6. **Domain**: Do you need custom domain for database? (optional)

## Estimated Timeline

| Phase | Duration | Notes |
|-------|----------|-------|
| Planning | 1 day | Review docs, make decisions |
| VPS Setup | 2 days | Install software, configure security |
| Code Migration | 1 week | Update all files, test thoroughly |
| Testing | 3 days | Load testing, bug fixes |
| **Migration Day** | **3 hours** | **Live migration** |
| Monitoring | 1 week | Verify stability |
| **Total** | **~2 weeks** | **Part-time work** |

---

**Status**: 📝 Planning phase - No code changes yet
**Next**: Review this document + VPS_MIGRATION_PROMPT.md, then decide on timeline
