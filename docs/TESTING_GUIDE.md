# Testing Guide - Avoiding Back-and-Forth

## 🎯 **The Problem**

We were doing too much push → test → fix → push cycle. Here's how to avoid it:

---

## ✅ **What Claude Can Do WITHOUT You**

### 1. **Syntax Validation** (Already Doing)

```bash
./check_before_commit.sh
```sql

This checks:

- Python syntax errors
- Missing imports (datetime, asyncio, etc.)
- Method calls match definitions
- Potential security issues

### 2. **What Claude NEEDS from You to Test More**

#### Option A: Database Access (Recommended)

Upload to GitHub (in a separate private repo or gist):

- **Database schema** (`pg_dump --schema-only`)
- **Sample data** (1-2 gaming sessions worth)

With this, Claude can:

- Test SQL queries locally
- Verify data transformations
- Check aggregation logic

#### Option B: Test Environment Variables

Create `.env.test` with fake values:

```env
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_DATABASE=test_db
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_pass
SSH_HOST=test.example.com
SSH_USER=testuser
SSH_KEY_PATH=/tmp/test_key
DISCORD_BOT_TOKEN=fake_token_for_testing
```text

This lets Claude test:

- Config loading
- Environment variable handling
- Default values

#### Option C: Sample Stats Files

Upload 2-3 example `.txt` files from:

```text

processed_stats/2025-11-14-213000-adlernest-round-1.txt
processed_stats/2025-11-14-213000-adlernest-round-2.txt

```bash

This lets Claude test:

- Stats parsing
- Data validation
- File processing

---

## 🚀 **Recommended Workflow**

### **For You (Before Starting Session):**

1. Upload database dump (if you haven't already)
2. Upload 2-3 sample stats files
3. Tell Claude: "I've uploaded test data, work on X without me"

### **For Claude (During Session):**

1. Make changes
2. Run `./check_before_commit.sh`
3. Test with sample data (if available)
4. Only commit when ALL checks pass
5. Make ONE final commit for you to test

### **For You (After Claude is Done):**

1. Pull once
2. Test once
3. Report if anything breaks
4. Otherwise, we're done! ✅

---

## 📊 **What You Can Upload to GitHub** (Safe)

✅ **Safe to upload publicly:**

- Database schema (no data, just structure)
- Sample stats files (redact player names if you want)
- `.env.example` (already public)

✅ **Safe in PRIVATE repo:**

- Database dump with real data
- Full `.env.test` with fake credentials

❌ **NEVER upload:**

- Real Discord bot token
- Real SSH private keys
- Real database passwords
- Production `.env` file

---

## 🔧 **How to Create Test Data**

### Database Schema

```bash
pg_dump -h localhost -U etlegacy -d etlegacy_stats --schema-only > schema.sql
```text

### Sample Data (2 sessions)

```bash
pg_dump -h localhost -U etlegacy -d etlegacy_stats \
  --data-only \
  --table=rounds \
  --table=player_comprehensive_stats \
  --table=weapon_comprehensive_stats \
  --table=session_teams \
  > sample_data.sql
```text

### Stats Files

```bash
# Copy 2-3 example files
cp processed_stats/2025-11-14-*.txt ./test_data/
```

---

## 💡 **Bottom Line**

**With test data**, Claude can finish entire features without bothering you.
**Without test data**, we're stuck in the push → test → fix loop.

**Your call!** Either way works, but test data = faster development. 🚀
