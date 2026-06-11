# Website-first roadmap (2026-06)

> **Vizija lastnika**: website postane PRIMARNI interface za igralce; Discord bot
> ostane del ekosistema, a skrčen na **pipeline + import + monitoring + notifikacije**
> (voice detection, SSH monitor, Lua webhook, Discord obvestila). Userji bota ne
> rabijo več za poizvedbe.

## Stanje (gap analiza, 2026-06-11)

Bot ima ~107 ukazov v 20 cogih. Website (legacy JS, 48 backend routerjev) danes
pokriva veliko večino **read-heavy stats** poizvedb (leaderboard, records,
sessions, last_session, story/smart-stats, hall-of-fame, proximity družina,
skill rating, awards, availability pregled, uploads). Glavne luknje so
**interaktivne/community** funkcije in **per-player analitika**, ki živi samo
kot bot text output.

### Kaj OSTANE na botu (by design)
- voice detection + session auto-monitoring, SSH endstats monitor, Lua webhook sprejem
- Discord notifikacije (round embeds, poll ping, achievements announce)
- ops ukazi (`!sync_*`, `!backup_db`, `!health`, `!correlation_status`, rcon/server_control)
  — admini smo trije, bot je za to čisto dober interface; web admin panel NI prioriteta.

## Prioritete za web (user-facing first)

### P1 — Account & identiteta (most do vsega ostalega)
1. **Link management UI** (`!link`/`!unlink`/`!myaliases`/`!setname` → web):
   stran "My account" po Discord OAuth loginu — poveži game GUID (search +
   autocomplete po aliasih obstaja), pregled/izbira display imena, seznam aliasov.
   Backend za link/aliases večinoma obstaja (link cog logika → API).
2. **Auth role gating**: `user_permissions` tabela že obstaja — backend
   `require_admin` dependency + frontend skritje admin elementov. Predpogoj za
   vse kasnejše admin/write funkcije (in že za setname/unlink varnost).

### P2 — Community funkcije
3. **Predictions na webu**: javne strani (`!predictions`, `!prediction_stats`,
   `!prediction_leaderboard` → web): napovedi tekem, accuracy leaderboard.
   View-only najprej; oddaja napovedi prek weba kasneje.
4. **Matchup / nemesis / synergy**: head-to-head stran (igralec A vs B:
   killi, win%, skupne seje; nemesis = kdo te največkrat ubije). Rivalries
   backend delno obstaja — razširiti.
5. **Availability oddaja na webu**: `!avail` set prek weba (API obstaja, UI ne).

### P3 — Per-player analitika (bot text → web vizualno)
6. **Analytics zavihek na profilu**: `!consistency`, `!map_stats` (per-player
   map affinity), `!playstyle`, `!fatigue` → grafi na obstoječem profilu
   (vzorec: aim rose / competitive card iz #378).
7. **Achievements grid**: badge mreža s progress bari (achievement_system port).
8. **Compare 2 igralcev**: radar (legacy compare.js obstaja? preveri in razširi).

### P4 — Live & admin (kasneje / po potrebi)
9. **Live status widget**: server player count + aktivna seja (game_server_query
   service obstaja; polling, ne WebSocket za v1).
10. **Mini admin stran**: sync trigger + proximity import + prediction outcome
    update — šele ko P1 auth gating stoji; rcon/server control NAMENOMA ostane na botu.

## Vrstni red izvedbe
P1.1 (link UI) → P1.2 (role gating) → P2.3 (predictions view) → P2.4 (matchup)
→ P3.6 (analytics tab) → P2.5 (avail submit) → P3.7 (achievements) → P3.8
(compare) → P4. Vsak korak svoj PR; user-facing korak = takoj uporabna vrednost.

## Bot "diet" (vzporedno, ko web pokrije funkcijo)
Ko web funkcija stoji in je potrjena: bot ukaz dobi deprecation notico z linkom
na web stran (ukazov NE brišemo takoj — graceful sunset). Pipeline cogi
(automation, sync, webhook, link backend) ostanejo nedotaknjeni.
