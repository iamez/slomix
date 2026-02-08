# FastDL Assistance Plan (Draft) - 2026-02-03

## Goal
Help players who fail FastDL downloads by offering reliable manual download links
and clear install steps, without disrupting the live server or the bot’s safety
and anti-corruption features.

## Current Reality (What’s Failing)
- Server log shows repeated FastDL failures for `.pk3` files.
- ET falls back to slow in-game download, which can still fail.
- Players disconnect before downloads complete.

## Core Idea (MVP)
When a player needs a file, the bot can provide:
- The `.pk3` file as a **Discord attachment** (no hosting, no open ports).
- Clear instructions on where to copy the file.
- A reminder to close the game before copying files.

## What’s Realistic Now (Low Risk)
1. **Bot Command for Manual Help (Discord Attachments)**
   - New command: `!map_send <mapname>`
   - Bot pulls the `.pk3` from server via SSH and uploads to Discord.
   - Optionally include `!legacy_send` for the ET:Legacy pk3.
   - Enforce safe size limit + strict filename validation.

2. **Human-In-The-Loop Support**
   - Admins can manually send a link to a player.
   - If a user requests it in Discord, bot replies with file + steps.

## What’s Possible Later (Medium Risk / Needs Extra Data)
1. **Log Parser → Player Assist**
   - Monitor server logs for download failures.
   - Detect missing filenames and generate a suggested response.
   - Requires mapping in-game name → Discord ID (via `!link`).

2. **Auto-DM / Auto-Ping**
   - Only if the player is linked and opted in.
   - Without linking, the bot can only post in a support channel.

## “Sci‑Fi” / Not Feasible Yet
- Auto-fix missing files without player action.
- Automatically pushing files directly into client’s game folder.
- Accurate Discord DM without player linking.

## Recommended Rollout (Safe)
1. **Phase 1 (Manual Assist)**
   - Add `!map_send` to upload `.pk3` as a Discord attachment.
   - Strictly validate filename and size before sending.

2. **Phase 2 (Light Automation)**
   - Add optional log watcher that detects failures and posts a suggestion
     in a staff channel (no DM yet).

3. **Phase 3 (Player Opt‑In)**
   - Add `!link` requirement + opt-in flag.
   - Bot can DM players when their in-game name appears in download failures.

## Install Steps Template (for Bot Reply)
1. Close the game.
2. Download the `.pk3`.
3. Copy to:
   - `etmain/` for maps
   - `legacy/` for ET:Legacy pk3
4. Restart the game.

## Safety / Anti‑Corruption Notes
- Do **not** auto‑delete or modify server files.
- Only send `.pk3` files from explicit directories.
- Validate filenames to prevent path traversal.
- Enforce a strict max file size (Discord limits vary by server/boost level).

## Testing Checklist
- Test sending a small `.pk3` to Discord (ensure size limit is respected).
- Verify client can join after manual install.

## Rollback
- Disable the bot command.
- No changes to core bot processing pipeline required.
