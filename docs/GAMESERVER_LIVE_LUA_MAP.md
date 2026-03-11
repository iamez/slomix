# Game Server Live Lua Map

Created: 2026-03-07

Purpose:
- Record the Lua files currently running on `puran.hehe.si`
- Keep a stable reference for repo sync decisions
- Avoid rediscovering the live module set from server logs every time

## Live Server

- Host: `puran.hehe.si`
- SSH: `et@91.185.207.163:48101`
- ET root: `/home/et/etlegacy-v2.83.1-x86_64`
- Game dir: `/home/et/etlegacy-v2.83.1-x86_64/legacy`
- Lua dir: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts`
- Runtime log: `/home/et/.etlegacy/legacy/etconsole.log`

## Active Server Start

The live process is started with:

```bash
/home/et/etlegacy-v2.83.1-x86_64/etlded.x86_64 +exec vektor.cfg
```

The config file is:

- `/home/et/etlegacy-v2.83.1-x86_64/etmain/vektor.cfg`

## Live Lua Modules

The actual loaded modules are confirmed by `etconsole.log`, not just by static cfg files.

Active modules:

- `luascripts/team-lock`
- `c0rnp0rn8.lua`
- `endstats.lua`
- `luascripts/proximity_tracker.lua`
- `luascripts/stats_discord_webhook.lua`

## Important Mismatch

Static config and live runtime do not fully agree.

- `/home/et/etlegacy-v2.83.1-x86_64/etmain/legacy.cfg` still contains:
  - `set lua_modules "luascripts/team-lock c0rnp0rn7.lua endstats.lua luascripts/stats_discord_webhook.lua"`
- But live `etconsole.log` shows:
  - `setl lua_modules luascripts/team-lock c0rnp0rn8.lua endstats.lua luascripts/proximity_tracker.lua luascripts/stats_discord_webhook.lua`

Rule:
- Treat `etconsole.log` as the source of truth for what is actually loaded.

## Live File Paths

- `c0rnp0rn8.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/c0rnp0rn8.lua`
- `endstats.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/endstats.lua`
- `stats_discord_webhook.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`
- `proximity_tracker.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/proximity_tracker.lua`
- `team-lock.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/team-lock.lua`

## Repo Mapping

Keep these mirrored locally:

- Proximity:
  - [proximity_tracker.lua](/home/samba/share/slomix_discord/proximity/lua/proximity_tracker.lua)
- Non-proximity game-server scripts:
  - [c0rnp0rn8.lua](/home/samba/share/slomix_discord/vps_scripts/c0rnp0rn8.lua)
  - [endstats.lua](/home/samba/share/slomix_discord/vps_scripts/endstats.lua)
  - [stats_discord_webhook.lua](/home/samba/share/slomix_discord/vps_scripts/stats_discord_webhook.lua)
  - [team-lock.lua](/home/samba/share/slomix_discord/vps_scripts/team-lock.lua)

## Hashes Captured On 2026-03-11

- `c0rnp0rn8.lua`
  - `ec919bfa065f552ad6e0fffda9a784e359f960fd698079033887706139ac08b3`
- `endstats.lua`
  - `fd18f765a8df65c51a153dd601a396256478e95e9d82451b0fb98c9f69b36561`
- `stats_discord_webhook.lua`
  - `06d669aa6c7dd34922bf2817f573662b73cbccb59099c0fce86fbbe33cd0258f`
- `team-lock.lua`
  - `7b0e6c11b1d64195852446d6a9c276917e2a4194988f3f0787777a8af091c7c1`
- `proximity_tracker.lua`
  - `1a32a3a6eb9ba9d138d7b7a10c648abbe6150387832df924d3241299214b4984` (v5.0 — upgraded from v4.2 `85bb9cf0` on 2026-03-11)

## Practical Rule

When syncing or auditing game-server Lua:

1. Check live `etconsole.log`
2. Confirm loaded file paths
3. Pull current remote copies
4. Mirror non-proximity scripts into `vps_scripts/`
5. Mirror proximity only into `proximity/lua/`
