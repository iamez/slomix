# ============================================================================
# SIMPLE LAST_SESSION FIX - JUST SPLIT INTO MULTIPLE EMBEDS
# ============================================================================
"""
Simple solution: When weapon mastery gets too long, just send multiple embeds!

Changes:
1. Keep showing ALL players
2. Keep showing ALL weapons per player
3. When an embed field approaches 1024 chars, just send it and start a new one
4. Add delays between sends to avoid rate limits

NO TRUNCATION. NO REMOVED PLAYERS. JUST MULTIPLE MESSAGES.
"""

# Replace this section in your existing last_session command
# Find where it says "MESSAGE 5: Weapon Mastery Breakdown"

# ═══════════════════════════════════════════════════════
# MESSAGE 5+: Weapon Mastery Breakdown (Multiple Embeds)
# ═══════════════════════════════════════════════════════

# Group by player and get their weapons
player_weapon_map = {}
for player, weapon, kills, hits, shots, hs in player_weapons:
    if player not in player_weapon_map:
        player_weapon_map[player] = []
    acc = (hits / shots * 100) if shots > 0 else 0
    hs_pct = (hs / hits * 100) if hits > 0 else 0
    weapon_clean = weapon.replace('WS_', '').replace('_', ' ').title()
    player_weapon_map[player].append(
        (weapon_clean, kills, acc, hs_pct, hs, hits, shots)
    )

# Convert revives data
player_revives = {player: revives for player, revives in player_revives_raw}

# Sort players by total kills - SHOW ALL PLAYERS
sorted_players = sorted(
    player_weapon_map.items(),
    key=lambda x: sum(w[1] for w in x[1]),
    reverse=True
)

# Create weapon mastery embeds - SPLIT AS NEEDED
weapon_embeds = []
current_embed = discord.Embed(
    title="🎯 Weapon Mastery Breakdown",
    description=f"Complete weapon statistics for all {len(sorted_players)} players",
    color=0x57F287,
    timestamp=datetime.now(),
)

current_field_count = 0

for player, weapons in sorted_players:
    # Calculate player overall stats
    total_kills = sum(w[1] for w in weapons)
    total_shots = sum(w[6] for w in weapons)
    total_hits = sum(w[5] for w in weapons)
    overall_acc = (total_hits / total_shots * 100) if total_shots > 0 else 0
    revives = player_revives.get(player, 0)
    
    # Build weapon text for this player - SHOW ALL WEAPONS
    weapon_text = f"**{total_kills} kills** • **{overall_acc:.1f}% ACC**"
    if revives > 0:
        weapon_text += f" • 💉 **{revives} revived**"
    weapon_text += "\n"
    
    # Add ALL weapons (not just top 3)
    for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
        weapon_text += f"• {weapon}: `{kills}K` `{acc:.0f}% ACC` `{hs} HS ({hs_pct:.0f}%)`\n"
    
    # Check if this field would exceed Discord limits
    # Discord limits: 25 fields per embed, 1024 chars per field value
    if current_field_count >= 25 or len(weapon_text) > 1024:
        # This embed is full - save it and start a new one
        weapon_embeds.append(current_embed)
        current_embed = discord.Embed(
            title="🎯 Weapon Mastery Breakdown (continued)",
            description=f"Part {len(weapon_embeds) + 1}",
            color=0x57F287,
            timestamp=datetime.now(),
        )
        current_field_count = 0
    
    # If a SINGLE player's weapons exceed 1024 chars, split their weapons across embeds
    if len(weapon_text) > 1024:
        # Split this player's weapons into chunks
        weapon_chunks = []
        current_chunk = f"**{total_kills} kills** • **{overall_acc:.1f}% ACC**"
        if revives > 0:
            current_chunk += f" • 💉 **{revives} revived**"
        current_chunk += "\n"
        
        for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
            weapon_line = f"• {weapon}: `{kills}K` `{acc:.0f}% ACC` `{hs} HS ({hs_pct:.0f}%)`\n"
            
            # If adding this weapon would exceed limit, start new chunk
            if len(current_chunk) + len(weapon_line) > 900:  # Leave buffer
                weapon_chunks.append(current_chunk)
                current_chunk = ""
            
            current_chunk += weapon_line
        
        # Add remaining chunk
        if current_chunk:
            weapon_chunks.append(current_chunk)
        
        # Add each chunk as a separate field
        for i, chunk in enumerate(weapon_chunks):
            if current_field_count >= 25:
                # Start new embed
                weapon_embeds.append(current_embed)
                current_embed = discord.Embed(
                    title="🎯 Weapon Mastery Breakdown (continued)",
                    description=f"Part {len(weapon_embeds) + 1}",
                    color=0x57F287,
                    timestamp=datetime.now(),
                )
                current_field_count = 0
            
            field_name = f"⚔️ {player}" if i == 0 else f"⚔️ {player} (continued)"
            current_embed.add_field(
                name=field_name,
                value=chunk.rstrip(),
                inline=False
            )
            current_field_count += 1
    else:
        # Normal case - player's weapons fit in one field
        current_embed.add_field(
            name=f"⚔️ {player}",
            value=weapon_text.rstrip(),
            inline=False
        )
        current_field_count += 1

# Add the last embed if it has content
if current_field_count > 0:
    weapon_embeds.append(current_embed)

# Send ALL weapon embeds with delays
for i, embed in enumerate(weapon_embeds):
    embed.set_footer(text=f"Session: {latest_date} • Page {i+1}/{len(weapon_embeds)}")
    await ctx.send(embed=embed)
    # Add delay between embeds to avoid rate limits (except for last one)
    if i < len(weapon_embeds) - 1:
        await asyncio.sleep(3)  # 3 second delay between embeds

logger.info(f"✅ Sent {len(weapon_embeds)} weapon mastery embeds")
