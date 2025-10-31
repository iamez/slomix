# 🔧 ALIAS FIX - MANUAL PATCH INSTRUCTIONS

## ⚠️ CRITICAL: DO NOT REPLACE THE ENTIRE FILE!

**Current bot:** 9,282 lines
**ultimate_bot_fixed.py:** 8,069 lines
**Difference:** Would lose 1,213 lines of code!

Instead, apply this as a **MANUAL PATCH** - add two small code blocks.

---

## 📍 STEP 1: Find the Location

Open `bot/ultimate_bot.py` and search for:

```python
async def _insert_player_stats(
```

Scroll to the **END** of this method. You'll see something like:

```python
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """,
            values,
        )

    async def post_round_summary(self, file_info, result):
```

---

## ➕ STEP 2: Add the Method Call

**After line with `values,` and closing `)`, BEFORE the next method:**

Add this code:

```python
        """,
            values,
        )
        
        # 🔗 CRITICAL: Update player aliases for !stats and !link commands
        await self._update_player_alias(
            db,
            player.get('guid', 'UNKNOWN'),
            player.get('name', 'Unknown'),
            session_date
        )
    
    async def post_round_summary(self, file_info, result):
```

**Important:** Make sure indentation matches! The `await` should align with the code above it.

---

## ➕ STEP 3: Add the New Method

**Right after `_insert_player_stats` ends, BEFORE `post_round_summary`:**

Add this entire method:

```python
    async def _update_player_alias(self, db, guid, alias, last_seen_date):
        """
        Track player aliases for !stats and !link commands
        
        This is CRITICAL for !stats and !link to work properly!
        Updates the player_aliases table every time we see a player.
        """
        try:
            # Check if this GUID+alias combination exists
            async with db.execute(
                'SELECT times_seen FROM player_aliases WHERE guid = ? AND alias = ?',
                (guid, alias)
            ) as cursor:
                existing = await cursor.fetchone()
            
            if existing:
                # Update existing alias: increment times_seen and update last_seen
                await db.execute(
                    '''UPDATE player_aliases 
                       SET times_seen = times_seen + 1, last_seen = ?
                       WHERE guid = ? AND alias = ?''',
                    (last_seen_date, guid, alias)
                )
            else:
                # Insert new alias
                await db.execute(
                    '''INSERT INTO player_aliases (guid, alias, first_seen, last_seen, times_seen)
                       VALUES (?, ?, ?, ?, 1)''',
                    (guid, alias, last_seen_date, last_seen_date)
                )
            
            logger.debug(f"✅ Updated alias: {alias} for GUID {guid}")
            
        except Exception as e:
            logger.error(f"❌ Failed to update alias for {guid}/{alias}: {e}")
```

**Important:** This is a class method, so it should have **ONE** level of indentation (4 spaces).

---

## ✅ STEP 4: Verify

After adding both code blocks, your file should still have **~9,282 lines** (plus ~50 new lines from the patch).

You should now have:
- The call to `_update_player_alias` at end of `_insert_player_stats` ✅
- The `_update_player_alias` method definition ✅

---

## 🧪 STEP 5: Test Syntax

Before running, test that Python syntax is correct:

```bash
python -m py_compile bot/ultimate_bot.py
```

If no errors → syntax is good! ✅

---

## 🗄️ STEP 6: Run Backfill

```bash
python backfill_aliases.py bot/etlegacy_production.db
```

---

## 🚀 STEP 7: Restart Bot

```bash
python bot/ultimate_bot.py
```

Watch for log messages:
```
✅ Updated alias: PlayerName for GUID ABC12345
```

---

## 🧪 STEP 8: Test Commands

```
!stats PlayerName
!link
```

Should now work! ✅

---

## 📊 What Changed

**Lines added:** ~50
**Lines removed:** 0
**Commands lost:** 0 (Nothing lost!)
**Features added:** Alias tracking ✅

---

## ⚠️ If Something Goes Wrong

**Problem:** SyntaxError after editing
**Solution:** Check indentation - Python is strict about spaces

**Problem:** Method not found
**Solution:** Make sure you added the method definition

**Problem:** Still can't find players
**Solution:** Run backfill_aliases.py again

---

## 🎯 Summary

**DO:** Apply manual patch (add ~50 lines)
**DON'T:** Replace entire file (lose 1,213 lines)

**Result:** 
- Keep all 9,282 lines ✅
- Add alias tracking fix ✅
- !stats and !link work ✅
