# Proximity ET:L Lua Capabilities (2026-02-19)

## Scope
Quick capability summary from ET:Legacy Lua docs for proximity expansion planning.

## Confirmed capture paths
- Class/team identity:
  - `et.gentity_get(clientnum, "sess.playerType")` and `sess.sessionTeam`.
  - `CS_PLAYERS` configstring keys include class fields (`c`, `lc`) and team (`t`) for fallback parsing.
- Combat hooks:
  - `et_Damage(target, attacker, damage, damageFlags, meansOfDeath)` for incoming/outgoing damage timing.
  - `et_Obituary(victim, killer, meansOfDeath)` for kill closure and ground-truth outcome.
  - `et_WeaponFire(clientNum, weapon)` for shot intent timing (optional augmentation).
- Movement telemetry:
  - `et.gentity_get(..., "ps.origin")`, `"ps.velocity"`, `"ps.weapon"`, `"ps.pm_flags"`, `"ps.stats"` for path/sprint/stance context.
- Identity and metadata:
  - `et.trap_GetUserinfo(clientnum)` + `et.Info_ValueForKey(...)` for GUID/name keys.
  - `et.trap_GetConfigstring(...)` + `et.Info_ValueForKey(...)` for map/session/player config fallback.

## Practical implications for proximity
- Yes, class tracking is feasible and stable in Lua; proximity can report class composition, class-specific reactions, and class-based teamwork metrics.
- Damage-timestamp hooks are sufficient to derive:
  - return-fire reaction time,
  - dodge reaction time (paired with movement vectors),
  - teammate support reaction time.
- C0RN and proximity can coexist: C0RN keeps round stats; proximity can own sub-second positional/combat reaction analytics.

## Implementation note (2026-02-19)
- These capabilities are now wired in the active proximity stack:
  - tracker output: `REACTION_METRICS` + class tagging,
  - parser import: `proximity_reaction_metric`,
  - website endpoints: `/api/proximity/classes` and `/api/proximity/reactions`.

## Source links
- https://etlegacy-lua-docs.readthedocs.io/en/latest/functions.html
- https://etlegacy-lua-docs.readthedocs.io/en/latest/fields.html
- https://etlegacy-lua-docs.readthedocs.io/en/latest/misc.html
