# ═══════════════════════════════════════════════════════════════════════════
# QUICK REFERENCE: Code Changes for !last_session
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 1: Add denied_playtime to SQL query
# ═══════════════════════════════════════════════════════════════════════════

# Find the SELECT statement and add this line after total_time_dead:
SUM(p.denied_playtime) as total_denied


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 2: Update player unpacking
# ═══════════════════════════════════════════════════════════════════════════

# BEFORE:
total_hs, hsk, total_seconds, total_time_dead = player[6:10]

# AFTER:
total_hs, hsk, total_seconds, total_time_dead, total_denied = player[6:11]


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 3: Add denied variable initialization
# ═══════════════════════════════════════════════════════════════════════════

# Add this line after the other variable assignments:
total_denied = int(total_denied or 0)


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 4: Calculate denied time display
# ═══════════════════════════════════════════════════════════════════════════

# Add these lines after time_dead_display:
# Calculate time denied
denied_minutes = int(total_denied // 60)
denied_seconds = int(total_denied % 60)
time_denied_display = f"{denied_minutes}:{denied_seconds:02d}"


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 5: Update display format
# ═══════════════════════════════════════════════════════════════════════════

# BEFORE:
top_text += (
    f"`{hsk} HSK ({hsk_rate:.1f}%)` • "
    f"`{total_hs} HS ({hs_rate:.1f}%)` • "
    f"⏱️ `{time_display}` • 💀 `{time_dead_display}`\n\n"
)

# AFTER:
top_text += (
    f"`{total_hs} HS ({hs_rate:.1f}%)` • "
    f"⏱️ `{time_display}` • 💀 `{time_dead_display}` • ⏳ `{time_denied_display}`\n\n"
)


# ═══════════════════════════════════════════════════════════════════════════
# OPTIONAL: Remove HSK calculation (no longer needed)
# ═══════════════════════════════════════════════════════════════════════════

# You can comment out or remove this line:
# hsk_rate = (hsk / kills * 100) if kills and kills > 0 else 0


# ═══════════════════════════════════════════════════════════════════════════
# COMPLETE UPDATED DISPLAY SECTION (Lines 1480-1520 approximately)
# ═══════════════════════════════════════════════════════════════════════════

if all_players:
    top_text = ""
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, player in enumerate(all_players):
        name, kills, deaths, dpm, hits, shots = player[0:6]
        total_hs, hsk, total_seconds, total_time_dead, total_denied = player[6:11]  # UPDATED

        # Handle NULL values
        kills = kills or 0
        deaths = deaths or 0
        dpm = dpm or 0
        hits = hits or 0
        shots = shots or 0
        total_hs = total_hs or 0
        hsk = hsk or 0
        total_seconds = total_seconds or 0
        total_time_dead = int(total_time_dead or 0)
        total_denied = int(total_denied or 0)  # NEW

        # Time played
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        time_display = f"{minutes}:{seconds:02d}"

        # Time dead
        dead_minutes = int(total_time_dead // 60)
        dead_seconds = int(total_time_dead % 60)
        time_dead_display = f"{dead_minutes}:{dead_seconds:02d}"

        # Time denied (NEW)
        denied_minutes = int(total_denied // 60)
        denied_seconds = int(total_denied % 60)
        time_denied_display = f"{denied_minutes}:{denied_seconds:02d}"

        # Calculate metrics
        kd_ratio = kills / deaths if deaths > 0 else kills
        acc = (hits / shots * 100) if shots and shots > 0 else 0
        hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0

        medal = medals[i] if i < len(medals) else f"{i + 1}."
        
        # Build display
        top_text += f"{medal} **{name}**\n"
        top_text += (
            f"`{kills}K/{deaths}D ({kd_ratio:.2f})` • "
            f"`{dpm:.0f} DPM` • "
            f"`{acc:.1f}% ACC ({hits}/{shots})`\n"
        )
        top_text += (
            f"`{total_hs} HS ({hs_rate:.1f}%)` • "
            f"⏱️ `{time_display}` • 💀 `{time_dead_display}` • ⏳ `{time_denied_display}`\n\n"
        )

    embed1.add_field(name="🏆 All Players", value=top_text.rstrip(), inline=False)


# ═══════════════════════════════════════════════════════════════════════════
# THAT'S IT!
# ═══════════════════════════════════════════════════════════════════════════
# Test with: !last_session
# You should see the new format with Time Denied and no HSK
