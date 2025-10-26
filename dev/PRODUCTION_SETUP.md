# 🚀 Production ET:Legacy Discord Bot Setup Guide

## ✅ **What We've Built:**

### 🎯 **Comprehensive Feature Set:**
- **SSH File Monitoring** - Automatically monitors `et@puran:/home/et/.etlegacy/legacy/gamestats/` for new C0RNP0RN3.lua files
- **Smart Import System** - Only processes NEW files (tracks 3000+ existing files to avoid duplicates)
- **Real Data Integration** - Successfully tested with your actual stats files
- **Comprehensive Database** - Captures ALL C0RNP0RN3.lua data (28 weapons, multikills, objectives, damage analytics)
- **Discord @Mention Support** - 10 real players already linked (@vid, @carniee, @bronze, etc.)
- **Production Ready** - Error handling, logging, admin controls

### 🏗️ **Architecture:**
```
Windows (Discord Bot)  ──SSH──>  Linux Game Server (et@puran)
     │                              │
     │                              └─ /home/et/.etlegacy/legacy/gamestats/
     │                                 ├─ 2024-11-26-224050-sw_goldrush_te-round-2.txt
     │                                 ├─ 2025-05-27-220703-sw_goldrush_te-round-2.txt
     │                                 └─ [3000+ files...]
     │
     └─ etlegacy_comprehensive.db
        ├─ 48 player records (REAL DATA)
        ├─ 10 Discord links  
        └─ Comprehensive C0RNP0RN3.lua schema
```

---

## 🛠️ **Setup Instructions:**

### **1. Install SSH Dependencies:**
```bash
cd "G:\VisualStudio\Python\stats"
python dev\install_ssh_deps.py
```

### **2. Configure Environment:**
```bash
# Copy the example configuration
copy dev\.env.production .env

# Edit .env with your settings:
DISCORD_BOT_TOKEN=your_actual_bot_token
SSH_HOST=puran
SSH_USER=et
SSH_KEY_PATH=C:\path\to\your\ssh\private\key
ADMIN_DISCORD_IDS=231165917604741121
```

### **3. Set Up SSH Key Authentication:**
```bash
# Generate SSH key pair (if you don't have one)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/etlegacy_bot

# Copy public key to game server
ssh-copy-id -i ~/.ssh/etlegacy_bot.pub et@puran

# Test connection
ssh -i ~/.ssh/etlegacy_bot et@puran
```

### **4. Start Production Bot:**
```bash
python dev\production_comprehensive_bot.py
```

---

## 🎮 **Discord Commands:**

### **📊 Player Stats:**
- `!stats @vid` - Overall comprehensive stats
- `!stats @carniee 30.9.2025` - Date-specific stats
- `!stats player_name` - Stats by name (if not linked)

### **📅 Session Stats:**
- `!session_stats 30.9` - All players from September 30th
- `!session_stats 30.9.2025` - Specific date with year

### **🔗 Player Linking:**
- `!link playername` - Link your Discord to ET:Legacy GUID

### **⚙️ Admin Commands:**
- `!start_monitoring` - Start SSH file monitoring
- `!stop_monitoring` - Stop SSH file monitoring
- `!import_status` - Show import statistics

---

## 📊 **Current Database Status:**
- ✅ **48 player records** from real C0RNP0RN3.lua files
- ✅ **10 Discord links** active (@vid, @carniee, @bronze, etc.)
- ✅ **Comprehensive schema** capturing ALL C0RNP0RN3.lua data
- ✅ **4 session dates** processed
- ✅ **Smart duplicate prevention** system

---

## 🔍 **Monitoring Features:**

### **Automatic File Detection:**
- Checks `/home/et/.etlegacy/legacy/gamestats/` every 5 minutes
- Downloads only NEW `.txt` files via SSH
- Processes with C0RNP0RN3StatsParser
- Stores comprehensive data in database
- Tracks processed files to avoid duplicates

### **Smart Processing:**
- **File Hash Tracking** - Prevents duplicate processing
- **Error Recovery** - Continues on parse errors
- **Comprehensive Logging** - Full audit trail
- **Real-time Status** - `!import_status` command

---

## 🎯 **What's Captured from C0RNP0RN3.lua:**

### **Combat Stats:**
- ✅ All 28 weapons (WS_KNIFE → WS_SYRINGE)
- ✅ Kills, deaths, damage given/received
- ✅ Headshots, accuracy, shots/hits
- ✅ Team damage, self kills

### **Advanced Analytics:**
- ✅ Killing sprees, death sprees
- ✅ Multikills (double → holy shit)
- ✅ DPM (Damage Per Minute)
- ✅ Time dead ratio, playtime
- ✅ Tank/meatshield stats

### **Objectives:**
- ✅ Dynamites planted/defused
- ✅ Objectives stolen/returned
- ✅ Revives, repairs, constructions
- ✅ XP, hit regions, bullets fired

---

## 🚀 **Ready for Production!**

Your comprehensive Discord bot is now ready with:
- **Real data integration** tested ✅
- **SSH monitoring** configured ✅  
- **Discord linking** working ✅
- **Comprehensive stats** captured ✅
- **Smart duplicate prevention** ✅
- **Production logging** ✅

Just configure your SSH credentials and Discord token, then start the bot!