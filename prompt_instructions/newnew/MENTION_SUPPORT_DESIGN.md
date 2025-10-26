# 🎮 @MENTION SUPPORT FOR BOT COMMANDS
**Feature**: Social stats lookup using Discord mentions  
**Status**: 📋 Planned for Phase 3  
**Priority**: ⭐⭐⭐ HIGH (huge UX improvement!)

---

## 💡 THE IDEA

**Instead of**:
```
!stats vid        ← might find wrong player, need to know exact name
```

**Do this**:
```
!stats @vid       ← mentions Discord user, bot looks up their linked GUID
```

**Benefits**:
- 🎯 **Accurate** - No name guessing, uses verified link
- 🤝 **Social** - Natural Discord interaction
- 🚀 **Fast** - Instant lookup via discord_id
- 📊 **Complete** - Shows all aliases automatically

---

## 🎨 USER EXPERIENCE

### **Scenario: Looking up a friend**

**User types**:
```
!stats @vid
```

**Bot responds**:
```
📊 ET:Legacy Stats for @vid

╔══════════════════════════════════════╗
║  Player: vid (GUID: D8423F90)        ║
║  Also known as: v1d, vid-slo         ║
╚══════════════════════════════════════╝

🎯 Combat Stats
   Kills: 18,234 | Deaths: 12,456 | K/D: 1.46
   Damage: 2.4M | DPM: 342.5
   Accuracy: 23.4% | Headshots: 2,341

🎖️ Performance
   Games: 1,462 | Time: 234h 12m
   XP: 1,234,567 | Efficiency: 67.8%

🏆 Achievements
   Best Spree: 23 | MVP Awards: 45
   Dynamites: 234 | Revives: 1,234

Last seen: 2025-10-02 playing te_escape2
```

**What happened**:
1. ✅ Bot detected @mention
2. ✅ Extracted Discord ID: `509737538555084810`
3. ✅ Queried `player_links` → found GUID `D8423F90`
4. ✅ Queried `player_aliases` → found aliases
5. ✅ Aggregated stats from all aliases
6. ✅ Showed complete profile

---

### **Scenario: User not linked**

**User types**:
```
!stats @someuser
```

**Bot responds**:
```
⚠️ @someuser hasn't linked their ET:Legacy account yet!

They can link with:
   !link              ← Search for their player
   !link PlayerName   ← Direct name search
   !link GUID         ← If they know their GUID

Or you can help them:
   !link @someuser GUID   ← (requires permissions)
```

**Helpful and guides users to link!**

---

### **Scenario: Comparing with friend**

**User types**:
```
!compare @vid @wajs
```

**Bot responds**:
```
⚔️ HEAD-TO-HEAD: @vid vs @wajs

         │  vid (D8423F90)  │  wajs (FDA127DF)
─────────┼──────────────────┼──────────────────
Kills    │  18,234 ✅       │  15,678
Deaths   │  12,456          │  10,234 ✅
K/D      │  1.46 ✅         │  1.53 ✅✅
DPM      │  342.5 ✅        │  298.2
─────────┼──────────────────┼──────────────────
Winner   │  vid by 2 points │

Both play as: Medic 🏥
Recent matchup: 2025-10-02 on te_escape2
```

**(Future enhancement!)**

---

## 🔧 IMPLEMENTATION

### **Step 1: Detect @mention in command**

```python
@commands.command(name='stats')
async def stats(self, ctx, *, target: str = None):
    """Show player stats - supports names and @mentions"""
    
    # Case 1: No args - show user's own stats
    if not target:
        discord_id = str(ctx.author.id)
        # ... existing logic
        return
    
    # Case 2: @mention detected
    if ctx.message.mentions:
        mentioned_user = ctx.message.mentions[0]
        discord_id = str(mentioned_user.id)
        
        # Look up in player_links
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute('''
                SELECT et_guid, et_name 
                FROM player_links 
                WHERE discord_id = ?
            ''', (discord_id,)) as cursor:
                link = await cursor.fetchone()
        
        if not link:
            # User not linked - helpful message
            await ctx.send(
                f"⚠️ {mentioned_user.mention} hasn't linked their account yet!\n"
                f"They can link with: `!link` or `!link <player_name>`"
            )
            return
        
        guid, et_name = link
        
        # Get aliases
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute('''
                SELECT clean_name 
                FROM player_aliases 
                WHERE player_guid = ?
                ORDER BY last_seen DESC
                LIMIT 3
            ''', (guid,)) as cursor:
                aliases = await cursor.fetchall()
        
        alias_str = ', '.join([a[0] for a in aliases]) if aliases else et_name
        
        # Show stats with aliases
        # ... (use existing stats display logic with GUID)
        
    # Case 3: Regular name search
    else:
        player_name = target
        # ... existing name search logic
```

### **Step 2: Update player_links queries**

All existing `!stats` logic works, just need to:
1. ✅ Detect @mention first
2. ✅ Look up discord_id → GUID
3. ✅ Get aliases from player_aliases
4. ✅ Show stats (existing code)

### **Step 3: Add helpful errors**

```python
# If mention but not linked
embed = discord.Embed(
    title="⚠️ Account Not Linked",
    description=f"{mentioned_user.mention} hasn't linked their ET:Legacy account",
    color=0xFFA500
)
embed.add_field(
    name="How to Link",
    value=(
        "• `!link` - Search for your player\n"
        "• `!link PlayerName` - Find specific name\n"
        "• `!link GUID` - Link with your GUID"
    )
)
await ctx.send(embed=embed)
```

---

## 📊 BENEFITS

### **For Users**:
1. 🎯 **No typos** - Can't misspell @mention
2. 🤝 **Social** - Natural Discord interaction
3. 👥 **Discover** - See friends' ET stats
4. 🏆 **Compare** - Easy stat comparisons

### **For Community**:
1. 📈 **Engagement** - More bot usage
2. 🎮 **Competition** - Friendly rivalry
3. 📊 **Discovery** - Find active players
4. 🔗 **Network** - Connect Discord & game

### **For Bot**:
1. ⚡ **Fast** - Direct GUID lookup
2. ✅ **Accurate** - No name ambiguity
3. 🛡️ **Safe** - Verified links only
4. 📈 **Trackable** - Usage analytics

---

## 🎯 SUPPORTED COMMANDS

### **Phase 3A: Basic @mention support**
- ✅ `!stats @user` - Show linked user's stats
- ✅ `!stats` - Show your own stats
- ✅ `!stats name` - Still works (fallback)

### **Phase 3B: Advanced @mention** (Future)
- 📋 `!compare @user1 @user2` - Head-to-head comparison
- 📋 `!recent @user` - User's recent games
- 📋 `!weapons @user` - User's weapon stats
- 📋 `!link @user GUID` - Admin linking

### **Phase 3C: Social features** (Future)
- 📋 `!squad @user1 @user2 @user3` - Team stats
- 📋 `!challenge @user` - Challenge to match
- 📋 `!rivals` - Your most-played-against players

---

## 🔒 PRIVACY CONSIDERATIONS

### **What's visible**:
- ✅ Public ET:Legacy stats (already public in-game)
- ✅ Aliases (tracks name changes, helpful)
- ✅ Recent activity (last seen date)

### **What's NOT visible**:
- ❌ Discord DMs
- ❌ Server membership
- ❌ Personal info beyond game stats

### **User control**:
- ✅ `!unlink` - Users can disconnect anytime
- ✅ `!privacy` - See what's shared (future)
- ✅ Opt-in - Must explicitly `!link`

---

## 💻 CODE CHANGES NEEDED

### **Files to modify**:
1. `bot/ultimate_bot.py` - Add @mention detection to `!stats`
2. Already queries `player_links` table ✅
3. Already has GUID-based stat lookup ✅
4. Just need to add mention parsing!

### **Estimated effort**:
- ⏱️ **20-30 minutes** for basic @mention support
- ⏱️ **1-2 hours** for error handling + testing
- ⏱️ **30 minutes** for documentation

**Total**: ~2-3 hours for complete @mention feature

---

## 🧪 TESTING CHECKLIST

### **Happy path**:
- [ ] `!stats @linked_user` shows their stats
- [ ] `!stats` shows your stats (if linked)
- [ ] `!stats name` still works (name search)

### **Edge cases**:
- [ ] `!stats @unlinked_user` shows helpful message
- [ ] `!stats @self` shows your own stats
- [ ] `!stats @bot` handles gracefully
- [ ] Multiple @mentions - use first one

### **Error cases**:
- [ ] Invalid mention format
- [ ] Deleted Discord user
- [ ] Unlinked but GUID deleted from game DB
- [ ] Network timeout

---

## 📝 EXAMPLE USAGE IN DISCORD

```
User: !stats @vid
Bot: [Shows vid's complete ET:Legacy profile with aliases]

User: !stats @wajs
Bot: [Shows wajs's stats with recent games]

User: !stats
Bot: [Shows your own stats if you're linked]

User: !stats @newbie
Bot: ⚠️ @newbie hasn't linked yet! They can use !link

Admin: !link @newbie 1C747DF1
Bot: 🔗 Linking @newbie to s&o.lgz (GUID: 1C747DF1)
      React ✅ to confirm
```

**Natural, intuitive, social! 🎉**

---

## 🚀 ROLLOUT PLAN

### **Phase 1: Basic Implementation**
1. Add @mention detection to `!stats`
2. Query player_links for discord_id
3. Show existing stats display
4. Add "not linked" error message

### **Phase 2: Polish**
1. Add alias display in stats
2. Improve error messages
3. Add help text
4. Test with community

### **Phase 3: Social Features**
1. Add `!compare @user1 @user2`
2. Add `!recent @user`
3. Add squad/team features
4. Analytics tracking

---

## 🎯 SUCCESS METRICS

### **Adoption**:
- Target: 80% of active players linked within 1 month
- Measure: `SELECT COUNT(*) FROM player_links`

### **Usage**:
- Target: 50%+ of `!stats` commands use @mentions
- Measure: Command logs / analytics

### **Engagement**:
- Target: 2x increase in bot commands
- Measure: Before/after comparison

---

## 💡 FUTURE ENHANCEMENTS

### **Smart mentions**:
```
!stats vid          ← searches by name
!stats @vid         ← uses link (faster, accurate)
!stats discord:vid  ← explicit Discord lookup
!stats guid:D8423F90 ← explicit GUID lookup
```

### **Bulk operations**:
```
!squad @user1 @user2 @user3 @user4 @user5
→ Shows team composition, combined stats
```

### **Notifications**:
```
User joins server → Bot suggests !link
User plays game → Bot posts achievement to Discord
User breaks record → Automatic announcement
```

---

**Status**: 📋 **Ready to Implement**  
**Priority**: ⭐⭐⭐ **HIGH** (huge UX win!)  
**Effort**: ~2-3 hours  
**Impact**: 🚀 **Major** (transforms bot into social tool)  

**Let's build this! 🎮**
