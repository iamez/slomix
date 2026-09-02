# BACKLOG — kje sem ostal + kaj se je spremenilo ad hoc

> Pravilo za skoke: ko uporabnik vpraša nekaj IZVEN trenutnega taska,
> PREJ sem zapiši, kje si ostal; po fixu se vrni in vpiši, kaj si
> spremenil — tudi če si kaj pokvaril. Commit po vsakem zaključenem
> koraku, ne na koncu dneva.

## Trenutna pozicija

- (Fable, 2026-09-02) #881 v merge ciklu; naslednja rezina: player dodatki
  (4 poti). Ni prekinjenih skokov.

## Tehnični dolg / ideje (nikjer drugje zapisane)

- round-end burst: batch write (table.concat → ~64 KB kosi) namesto 8400
  posamičnih trap_FS_Write; PREJ en večer self meritev z v6.12.
- tracker mikro: cache `sv_maxclients` (isValidClient ga bere ob vsakem
  klicu); združi dve cohesion zanki (isti pari, ista razdalja dvakrat).
- webhook pending_retry_sweep: io.popen find vsakih 60 s tudi ob praznem
  bufferju — gate za fork.
- replay stran: playback canvas je imenovan follow-up (paritetna tarča ga
  ni imela); kill-outcomes `events` seznam (80 KB) se ne izrisuje.
- spider-web: information_state/beliefs se še ne izrisujejo; mesh za
  etl_supply ne obstaja (BSP ni izvožen).
- weapon-accuracy `weapon_breakdown` se napolni le pod player_guid filtrom
  — player rezina naj ga pokaže.
- lokalna past: generirani `src/api/generated/openapi.d.ts` je bil 2×
  zastarel ob typechecku → pred meritvijo `rm` (ali dodaj v pretypecheck).
- `.claude_session` (SessionEnd hook) je v gitignore; po izpadu `--resume`.
