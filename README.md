# 🎮 ET:Legacy Discord Stats Bot

> **Transform your ET:Legacy (Wolfenstein: Enemy Territory) gaming sessions into comprehensive statistics with beautiful Discord embeds!**

A fully-featured Discord bot that automatically tracks player statistics, displays detailed match results, and provides leaderboards for your ET:Legacy game server.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://github.com/Rapptz/discord.py)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)

---

## ✨ Features

### 📊 Comprehensive Statistics Tracking
- **53+ stat fields per player** - Kills, deaths, damage, accuracy, headshots, and more
- **Weapon statistics** - Per-weapon performance tracking
- **Objective stats** - Revives, construction, demolition, flag captures
- **Team scoring** - Track real team names across multi-round sessions

### 🤖 Discord Bot Commands
- `!last_session` - Show the most recent gaming session
- `!stats [player]` - Display individual player statistics
- `!leaderboard [type] [page]` - Rankings (12 types: kills, K/D, DPM, accuracy, headshots, etc.)
- `!link <name>` - Link your Discord account to your in-game profile
- `!sessions [month]` - Browse past sessions
- And more!

### 🔄 Automation Features (Optional)
- **SSH Monitoring** - Automatically download new stats from your game server
- **Voice Channel Detection** - Auto-start monitoring when players join voice
- **Real-time Updates** - Post round summaries as games complete

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- Discord bot token ([Create one here](https://discord.com/developers/applications))
- ET:Legacy server with `c0rnp0rn3.lua` mod installed

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/etlegacy-discord-bot.git
   cd etlegacy-discord-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the bot**
   ```bash
   cp .env.example .env
   # Edit .env with your Discord token and server IDs
   ```

4. **Create the database**
   ```bash
   python database/create_unified_database.py
   ```

5. **Import your stats** (if you have existing stats files)
   ```bash
   # Copy your stats files to local_stats/ folder
   python tools/simple_bulk_import.py local_stats/*.txt
   ```

6. **Run the bot**
   ```bash
   python bot/ultimate_bot.py
   ```

---

## ⚙️ Configuration

### Required Settings

Edit `.env` file with your Discord credentials:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
GUILD_ID=your_discord_server_id
STATS_CHANNEL_ID=channel_id_for_stats
```

### Optional: SSH Monitoring

Enable automatic stats downloading from your game server:

```env
SSH_ENABLED=true
SSH_HOST=your.gameserver.com
SSH_PORT=22
SSH_USER=username
SSH_KEY_PATH=~/.ssh/id_rsa
REMOTE_STATS_DIR=/path/to/gamestats
```

### Optional: Voice Channel Automation

Auto-start monitoring when players join voice channels:

```env
AUTOMATION_ENABLED=true
GAMING_VOICE_CHANNELS=voice_channel_id1,voice_channel_id2
ACTIVE_PLAYER_THRESHOLD=6
```

---

## 📖 Commands

### Statistics Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!last_session` | Show the most recent gaming session | `!last_session` |
| `!stats [player]` | Player statistics (or your linked account) | `!stats vid` |
| `!stats @user` | Stats for mentioned Discord user | `!stats @YourFriend` |
| `!leaderboard [type] [page]` | Top players rankings | `!lb dpm 2` |
| `!sessions [month]` | Browse past sessions | `!sessions 2025-10` |

### Leaderboard Types

- `kills` - Total kills
- `kd` - Kill/Death ratio
- `dpm` - Damage Per Minute
- `acc` - Accuracy percentage
- `hs` - Headshot percentage
- `dmg` - Total damage given
- `xp` - Total XP earned
- `revives` - Revives given
- `time` - Time played
- `obj` - Objective points
- `multi` - Multikills
- `spree` - Best killing spree

### Account Linking

| Command | Description | Example |
|---------|-------------|---------|
| `!link <name>` | Link your Discord to in-game name | `!link vid` |
| `!unlink` | Unlink your account | `!unlink` |

### Admin Commands

| Command | Description |
|---------|-------------|
| `!session_start` | Manually start monitoring |
| `!session_end` | Manually end monitoring |
| `!sync_stats` | Trigger SSH stats sync |

---

## 📊 Database Schema

The bot uses SQLite with a unified schema:

### Tables

- **sessions** - Game sessions (map, round, time)
- **player_comprehensive_stats** - Player performance (53 columns)
- **weapon_comprehensive_stats** - Per-weapon statistics
- **player_links** - Discord account linking
- **session_teams** - Team rosters for multi-round matches
- **processed_files** - Track imported stats files

### Schema Details

**player_comprehensive_stats** includes:
- Combat: kills, deaths, damage, gibs, accuracy
- Weapons: per-weapon stats (kills, headshots, hits, shots)
- Objectives: revives, construction, demolition, captures
- Support: health/ammo packs given
- Time: played, on each team
- XP: total and combat XP

---

## 🛠️ Tools

### Import Stats

Import stats files into database:
```bash
python tools/simple_bulk_import.py local_stats/*.txt
```

### Sync from Server

Download new stats via SSH:
```bash
python tools/sync_stats.py
```

### Manage Teams

Set up hardcoded team names for multi-round sessions:
```bash
python tools/create_session_teams_table.py
python tools/update_team_names.py
```

---

## 📁 Project Structure

```
etlegacy-discord-bot/
├── bot/
│   ├── ultimate_bot.py          # Main bot code
│   ├── community_stats_parser.py # Stats file parser
│   └── cogs/
│       └── synergy_analytics.py  # Optional: Player synergy
├── database/
│   └── create_unified_database.py # Database setup
├── tools/
│   ├── simple_bulk_import.py     # Import stats
│   ├── sync_stats.py             # SSH sync
│   └── update_team_names.py      # Team management
├── docs/
│   └── (Documentation files)
├── .env.example                  # Configuration template
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## 🎮 ET:Legacy Server Setup

### Install c0rnp0rn3.lua Mod

Your ET:Legacy server needs the `c0rnp0rn3.lua` statistics mod to generate stats files.

1. Download from: https://github.com/iamez/etlegacy-scripts
2. Install to your server's lua directory
3. Stats files will be generated in `gamestats/` folder

### Stats File Format

Files are named: `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`

Example: `2025-10-02-232818-erdenberg_t2-round-2.txt`

---

## 🔧 Troubleshooting

### Bot Not Responding?

1. Check bot has proper Discord permissions:
   - Read Messages
   - Send Messages
   - Embed Links
   - Attach Files

2. Verify bot token in `.env` is correct
3. Check bot has access to your stats channel

### Database Errors?

1. Ensure you used `create_unified_database.py` (creates 53-column schema)
2. Don't use `create_fresh_database.py` (creates 60 columns - incompatible!)
3. Delete database and recreate if schema is wrong

### Import Failing?

1. Check stats files are in correct format (c0rnp0rn3.lua v3.0+)
2. Verify files end with `.txt`
3. Check file permissions

### SSH Not Working?

1. Test SSH connection manually: `ssh user@host -p port`
2. Verify SSH key path in `.env`
3. Check remote stats directory exists

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📝 License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **ET:Legacy Team** - For the amazing Enemy Territory revival
- **iamez** - For the c0rnp0rn3.lua statistics mod
- **discord.py** - For the excellent Discord API library

---

## 📞 Support

Having issues? Check these resources:

- **GitHub Issues**: [Report bugs or request features](https://github.com/yourusername/etlegacy-discord-bot/issues)
- **ET:Legacy Discord**: Join the community
- **Documentation**: Check the `docs/` folder for detailed guides

---

## 🎯 Roadmap

- [ ] Web dashboard for stats visualization
- [ ] Player synergy/chemistry analytics
- [ ] Historical performance trends
- [ ] Match prediction system
- [ ] Custom embed themes
- [ ] Multi-server support

---

**Made with ❤️ for the ET:Legacy community**

*Last updated: October 7, 2025*
