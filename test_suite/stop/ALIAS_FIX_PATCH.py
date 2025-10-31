# ================================================================
# ALIAS FIX PATCH - Add this to your ultimate_bot.py
# ================================================================
# DO NOT REPLACE YOUR ENTIRE FILE!
# Just add these two code blocks to your existing bot.
# ================================================================

# ================================================================
# PART 1: ADD TO END OF _insert_player_stats METHOD
# ================================================================
# Location: Around line 8653, at the end of _insert_player_stats
# Find where the method ends (after the big INSERT query)
# Add this code BEFORE the next method definition:

        # 🔗 CRITICAL: Update player aliases for !stats and !link commands
        await self._update_player_alias(
            db,
            player.get('guid', 'UNKNOWN'),
            player.get('name', 'Unknown'),
            session_date
        )

# ================================================================
# PART 2: ADD THIS NEW METHOD
# ================================================================
# Location: Right after _insert_player_stats ends (around line 8654)
# Add this entire method definition:

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

# ================================================================
# THAT'S IT! Just these two additions.
# ================================================================
# After adding:
# 1. Save the file
# 2. Run: python backfill_aliases.py
# 3. Restart bot
# 4. Test: !stats YourName
# ================================================================
