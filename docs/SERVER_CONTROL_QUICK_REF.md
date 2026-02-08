# 🎮 Server Control Quick Reference

## Setup Checklist

- [ ] RCON configured in `vektor.cfg` with strong password
- [ ] RCON settings added to `.env` file
- [ ] Admin channel ID added to `.env` file
- [ ] Bot restarted and cog loaded successfully
- [ ] Tested `!server_status` command
- [ ] Tested `!list_maps` command (alias: `!map_list`)

---

## Essential Commands

### Server

- `!server_status` or `!status` - Check if online
- `!server_restart` - Restart server (requires ✅)

### Maps

- `!list_maps` or `!map_list` - Show all maps
- `!map_change <name>` - Change map
- `!map_add` + attach .pk3 - Upload new map

### Players

- `!rcon status` - List online players
- `!kick <id> <reason>` - Kick player
- `!say <message>` - Message to server

---

## .env Configuration

```bash
# RCON (Required)
RCON_ENABLED=true
RCON_HOST=puran.hehe.si
RCON_PORT=27960
RCON_PASSWORD=your_rcon_password

# Admin Channel (Required)
ADMIN_CHANNEL_ID=your_channel_id
```yaml

---

## Useful RCON Commands

| Command | Description |
|---------|-------------|
| `!rcon status` | Show players and map |
| `!rcon g_gametype` | Show current gametype |
| `!rcon cvarlist` | List all cvars |
| `!rcon map_restart` | Restart current map |
| `!rcon ref <id>` | Make player referee |

---

## Server Paths (Hardcoded)

- **Root:** `/home/et/etlegacy-v2.83.1-x86_64`
- **Binary:** `etlded.x86_64`
- **Config:** `vektor.cfg`
- **Maps:** `/home/et/etlegacy-v2.83.1-x86_64/etmain`
- **Screen:** `vektor`

---

## Troubleshooting

**RCON not working?**

```bash
# Test manually
nc -u puran.hehe.si 27960
# Type: rcon PASSWORD status
```text

**Can't use commands?**

- Make sure you're in the admin channel
- Check `ADMIN_CHANNEL_ID` matches your channel

**Upload fails?**

```bash
# Check permissions on server
ssh et@puran.hehe.si -p 48101
chmod 755 ~/etlegacy-v2.83.1-x86_64/etmain/
```

---

## Audit Log Location

`logs/server_control_access.log` - All admin actions logged here

---

## Security Notes

- ⚠️ Commands only work in admin channel
- ⚠️ All actions are logged locally
- ⚠️ Destructive actions require ✅ confirmation
- ⚠️ RCON password should be 32+ characters

---

**For detailed setup: See `docs/SERVER_CONTROL_SETUP.md`**
