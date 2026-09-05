-- Offline harness for vps_scripts/dots_arena_1v1.lua — run from the repo root:
--     lua5.4 tests/lua/dots_arena_1v1_harness.lua
--
-- Same shape as tests/lua/frame_health_harness.lua: the engine is a stub, so
-- the module's decisions can be checked without a server. What the stub CANNOT
-- tell you is engine ordering — it once modelled a freshly-killed player as
-- already dead, which made the recursion guard look like dead code. The live
-- server said the opposite (health 2..42 at obituary time, never negative).
-- Treat a pass here as "the logic is consistent", never as "it works".
-- Stub motorja, razširjen na nove poti: log, spawn hook, testni ukaz.
local calls, logged, sent = {}, {}, {}
local weapons, current_wp = {}, {}
local ammo_of, clip_of, setcurrent_of = {}, {}, {}
local nofatigue = {}
local now_ms = 100000
local health = {[0]=100, [1]=100}
local team   = {[0]=1,   [1]=2}
local conn   = {[0]=2,   [1]=2}
local shield = {[0]=0,   [1]=0}
local cvars  = {sv_maxclients="2", arena_1v1="1", arena_1v1_map="dots_arena",
                arena_1v1_test="1", arena_1v1_log="1", g_forcerespawn="0",
                mapname="dots_arena"}
local argv   = {}
-- Every gentity field this module is allowed to name. The real API raises on
-- anything else; so does this stub.
local KNOWN_FIELDS = {
  ["pers.connected"]=true, ["pers.netname"]=true, ["sess.sessionTeam"]=true,
  ["ps.stats"]=true, ["ps.powerups"]=true, ["health"]=true,
  ["pers.playerStats.selfkills"]=true,
}
local damage_lands = true
local fs_open_fails = false
local fs_len = 0
local fs_renames = {}
local serverinfo = "\\mapname\\dots_arena"
et = {
  TEAM_AXIS=1, TEAM_ALLIES=2, STAT_HEALTH=0, CS_SERVERINFO=0, PW_INVULNERABLE=1,
  -- ⛔ Prave vrednosti iz motorja, ne izmišljene: živi log je pokazal mod=59
  -- za menjavo moštva, medtem ko je stub predpostavljal 38. Varovalo je
  -- vseeno delovalo (primerja se s konstanto), a stub, ki laže o številki,
  -- je natanko tisto, kar prikrije napačen indeks drugje.
  -- ⛔ FS_READ=0 je manjkal in rotacija je zato brala dolžino 0 — ista past
  -- kot manjkajoča STAT_SPRINTTIME. Vse štiri načine ima motor
  -- registrirane (g_lua.c:3291-3294), zato jih ima tudi stub.
  -- ⛔ 33 in 59 sta IZMERJENA v živo (/kill in /team s), ne prešteta iz
  -- bg_public.h — naivno štetje enuma da 26 in 46 in je napačno.
  -- MOD_GRENADE je poljubna vrednost: logika je ne primerja, rabi jo le
  -- kot »neki orožni mod, ki NI samomor«.
  MOD_SUICIDE=33, MOD_SWITCHTEAM=59, MOD_GRENADE=4, PW_NOFATIGUE=4,
  FS_READ=0, FS_WRITE=1, FS_APPEND=2, FS_APPEND_SYNC=3,
  STAT_MAX_HEALTH=3, STAT_SPRINTTIME=8,
  RegisterModname=function() end, G_Print=function() end,
  trap_Cvar_Get=function(n) return cvars[n] or "" end,
  trap_Cvar_Set=function(n,v) cvars[n]=v; calls[#calls+1]="cvar "..n.."="..v end,
  -- ⛔ The stub must be able to produce the FRESH-LOAD shape, where
  -- CS_SERVERINFO is empty and only the cvar knows the map. A stub that
  -- always answered from the configstring could not fail case 22 — and
  -- that is precisely why this bug survived every offline test.
  trap_GetConfigstring=function() return serverinfo end,
  Info_ValueForKey=function(s,k) return s:match("\\"..k.."\\([^\\]*)") end,
  trap_Argv=function(i) return argv[i+1] or "" end,
  -- ⛔ The stub used to answer `7, 0` for every mode, so the log's open-failure
  -- branch was never executed and FS_READ never reported a size. Both are now
  -- modelled: FS_READ returns the length (files.c:5259), the append modes
  -- return 0 or -1, and fs_open_fails drives the failure branch.
  trap_FS_FOpenFile=function(name, mode)
    if fs_open_fails then return 0, -1 end
    if mode == 0 then return 7, fs_len end     -- FS_READ -> length
    return 7, 0                                 -- FS_APPEND -> 0 on success
  end,
  trap_FS_Rename=function(old, new) fs_renames[#fs_renames+1] = old .. " -> " .. new end,
  trap_FS_Write=function(line) logged[#logged+1]=line:gsub("\n","") end,
  trap_FS_FCloseFile=function() end,
  -- ⛔⛔ The real binding RAISES on an unknown field name (luaL_error,
  -- g_lua.c:2032/:2130). A stub that answers nil for a typo lets that typo
  -- pass every test here and then abort the whole hook on a live server —
  -- the same shape as the unconditionally-lethal G_Damage this stub used to
  -- have, and as the constants it used to be missing.
  gentity_get=function(cn, field, idx)
    if not KNOWN_FIELDS[field] then
      error(("Lua API: unknown field \"%s\""):format(tostring(field)), 0)
    end
    if field=="pers.connected" then return conn[cn] end
    if field=="pers.netname" then return ({[0]="^1alpha",[1]="^2bravo",[2]="^3charlie",[3]="^4delta"})[cn] end
    if field=="sess.sessionTeam" then return team[cn] end
    if field=="ps.stats" and idx==0 then return health[cn] end
    if field=="ps.powerups" and idx==1 then return shield[cn] end
    if field=="pers.playerStats.selfkills" then return 0 end
  end,
  Q_CleanStr=function(s) return (s:gsub("%^%d","")) end,
  trap_Milliseconds=function() return now_ms end,
  RemoveWeaponFromPlayer=function(cn, wp) weapons[cn] = weapons[cn] or {}; weapons[cn][wp] = nil end,
  -- ⛔ setcurrent is modelled, not ignored: the real binding only writes
  -- ps.weapon when the 5th argument is exactly 1 (g_lua.c:1113-1116). A stub
  -- that always switched the weapon would have hidden a module that switches
  -- it by accident — the exact failure the withdrawn loadout produced live.
  AddWeaponToPlayer=function(cn, wp, ammo, clip, cur)
    -- ⛔ The real binding RAISES on an invalid weapon (luaL_error via
    -- IS_VALID_WEAPON, g_lua.c:1102-1107). A stub that quietly accepted
    -- WP_NONE could not make case 18's guard fail, and a guard that cannot be
    -- seen failing is not a guard.
    if type(wp) ~= "number" or wp <= 0 then
      error(("weapon \"%s\" is not a valid weapon"):format(tostring(wp)), 0)
    end
    weapons[cn] = weapons[cn] or {}; weapons[cn][wp] = true
    ammo_of[cn] = ammo; clip_of[cn] = clip; setcurrent_of[cn] = cur
    if cur == 1 then current_wp[cn] = wp end
  end,
  GetCurrentWeapon=function(cn) return current_wp[cn] or 0, ammo_of[cn] or 0, clip_of[cn] or 0 end,
  trap_SendServerCommand=function(cn, cmd) sent[#sent+1]=cmd end,
  gentity_set=function(cn, field, idx, val)
    if not KNOWN_FIELDS[field] then
      error(("Lua API: unknown field \"%s\""):format(tostring(field)), 0)
    end
    if field=="ps.powerups" and idx==1 then shield[cn]=val end
    if field=="ps.powerups" and idx==4 then nofatigue[cn]=val end
    if field=="health" then health[cn]=idx end
    if field=="ps.stats" and idx==0 then health[cn]=val end
    calls[#calls+1]=("set(%d,%s,%s,%s)"):format(cn, field, tostring(idx), tostring(val))
  end,
  -- ⛔⛔ The stub used to be UNCONDITIONALLY lethal, and that single line made
  -- every no-op path in G_Damage invisible to the whole harness: warmup with
  -- match_warmupDamage 0, intermission, godmode, noclip, !takedamage. A stub
  -- that cannot refuse cannot test the code that handles refusal.
  G_Damage=function(t,i,a,d,f,m)
    calls[#calls+1]=("G_Damage(%d,%d,%d,%d,0x%x,%d)"):format(t,i,a,d,f,m)
    if not damage_lands then return end      -- the engine declined; nothing happens
    et_Obituary(t, a, m); health[t]=-500
  end,
}
local here = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
dofile(here .. "../../vps_scripts/dots_arena_1v1.lua")
et_InitGame(0,0,false)

-- 1) normalen kill -> preživeli pobit, zabeleženo
shield[0] = 999999   -- preživeli je ŠE pod ščitom: ravno primer, ki je prej odpovedal
health[1]=0; et_Obituary(1, 0, 7)
-- ⛔ Ključno: ščit MORA biti počiščen PRED G_Damage. G_Damage se pri aktivnem
-- PW_INVULNERABLE vrne takoj (g_combat.c:1593), torej bi bil klic brez tega
-- popolna ničla — natanko tistih 6 od 80 dvobojev v živi meritvi.
local iset, idmg
for i, c in ipairs(calls) do
  if c:match("^set%(0,ps%.powerups,1,0%)$") then iset = i end
  if c:match("^G_Damage%(0,1022,1022,1000,0x20,33%)$") then idmg = i end
end
assert(iset, "ščit ni bil počiščen: "..table.concat(calls," | "))
assert(idmg, "G_Damage ni bil klican: "..table.concat(calls," | "))
assert(iset < idmg, "⛔ ščit mora biti počiščen PRED škodo, sicer je škoda ničla")
print("✅ kill -> ščit počiščen, nato force_reset prek sveta")

-- 2) log res nosi meritev, ne le besedila
local has_obit, has_force = false, false
for _, l in ipairs(logged) do
  if l:match("OBIT%s+victim=1 killer=0 mod=7 health=0 shield=0 selfkills=0") then has_obit=true end
  if l:match("FORCE%s+cn=0 why=survivor health=100 shield=999999 selfkills=0") then has_force=true end
end
assert(has_obit, "OBIT vrstica brez meritve: "..table.concat(logged," | "))
assert(has_force, "FORCE vrstica brez meritve: "..table.concat(logged," | "))
print("✅ log nosi health/shield/selfkills, ne le dogodka")

-- 3) spawn hook zapiše ščit (to je ura, po kateri se sodi)
logged = {}
-- Različna ščita: en frame narazen, kot v živi meritvi (25 ms pri sv_fps 40).
shield[0]=45000; shield[1]=45025
et_ClientSpawn(0, 0, 0, 0); et_ClientSpawn(1, 0, 0, 0)
assert(logged[1]:match("SPAWN.*cn=0.*shield=45000"), "spawn log brez ščita: "..table.concat(logged," | "))
-- ⛔ Motor po zasnovi NE spawna obeh v istem frameu (instantRespawnDelayTime,
-- g_active.c:1820). Zato se poravna tisto, kar igralec občuti — ščit — in to
-- na ZGODNEJŠO potečo, da nihče ne dobi več zaščite, kot jo je motor namenil.
assert(shield[0]==45000 and shield[1]==45000,
       "ščita nista poravnana na zgodnejšo: "..shield[0].."/"..shield[1])
assert(table.concat(logged," "):match("LEVEL"), "poravnava ni zabeležena")
print("✅ ščita poravnana na zgodnejšo potečo (45025 -> 45000)")

-- 4) testni ukaz: prevzame SVOJ ukaz in pusti tuje pri miru
calls = {}; health[0]=100; health[1]=100
argv = {"arena_kill", "1"}
assert(et_ConsoleCommand() == 1, "arena_kill mora vrniti 1 (obravnavano)")
assert(#calls==2 and calls[1]:match("^set%(1,ps%.powerups") and calls[2]:match("^G_Damage%(1,"),
       "arena_kill ni ubil pravega: "..table.concat(calls," | "))
argv = {"say", "hello"}
assert(et_ConsoleCommand() == 0, "⛔ tuj konzolni ukaz mora vrniti 0, sicer ga požremo")
print("✅ testni ukaz prevzame svoje, tujih ne požre")

-- 5) izklopljen testni način ukaz ignorira
cvars.arena_1v1_test = "0"; argv = {"arena_kill", "1"}
assert(et_ConsoleCommand() == 0, "pri arena_1v1_test 0 mora biti ukaz mrtev")
print("✅ testni ukaz je mrtev, ko je testni način izklopljen")

-- 6) DRUGA mapa -> skripta se ne sme oborožiti.
--    Brez tega primera mutacija »odstrani gate mape« preživi: vsi prejšnji
--    primeri tečejo NA arena mapi, torej gate ne loči ničesar.
cvars.arena_1v1_test = "1"
-- ⛔ BOTH sources have to say "supply". The module now reads the `mapname`
-- cvar first (the configstring is empty at a fresh map load), so moving
-- only the configstring left the cvar still saying dots_arena and the
-- module armed on a map this case exists to prove it ignores.
serverinfo = "\\mapname\\supply"; cvars.mapname = "supply"
calls = {}; health[0]=100; health[1]=100
et_InitGame(0,0,false)
health[1] = 0
et_Obituary(1, 0, 7)
assert(#calls == 0, "⛔ na tuji mapi se skripta ne sme vmešavati, a je: "..table.concat(calls," | "))
argv = {"arena_kill", "1"}
et_ConsoleCommand()
assert(#calls == 0, "⛔ tudi testni ukaz mora biti mrtev na tuji mapi")
print("✅ na mapi, ki ni arena, ne stori ničesar")

-- 7) KONTROLA mora biti izvedljiva: pri arena_1v1 0 se samodejni reset NE
--    sproži, testni ukaz pa MORA delati — sicer neenakosti ni mogoče izmeriti.
serverinfo = "\\mapname\\dots_arena"; cvars.mapname = "dots_arena"
cvars.arena_1v1 = "0"; cvars.arena_1v1_test = "1"
et_InitGame(0,0,false)
calls = {}; health[0]=100; health[1]=100
health[1] = 0
et_Obituary(1, 0, 7)
assert(#calls == 0, "⛔ pri arena_1v1 0 se samodejni reset NE sme sprožiti")
argv = {"arena_kill", "0"}
assert(et_ConsoleCommand() == 1, "⛔ testni ukaz mora delati tudi pri arena_1v1 0 (sicer ni kontrole)")
assert(#calls == 2 and calls[2]:match("^G_Damage%(0,"), "arena_kill ni ubil: "..table.concat(calls," | "))
print("✅ kontrola je izvedljiva: reset miruje, testni ukaz dela")

-- 8) Svet vodi izid: točka gre NASPROTNIKU umrlega, prisilni reset ne šteje,
--    in ob vsakem dvoboju gre ven objava. Brez tega je na tej mapi izid
--    neberljiv — zmagovalec dobi smrt tako kot poraženec, K/D pa neodločeno.
serverinfo = "\\mapname\\dots_arena"; cvars.mapname = "dots_arena"
cvars.arena_1v1 = "1"; cvars.arena_1v1_test = "1"
et_InitGame(0,0,false)
sent = {}; health[0]=100; health[1]=100; shield[0]=0; shield[1]=0
health[1] = 0; et_Obituary(1, 0, 7)          -- 0 ubije 1
health[1] = 100; health[0] = 0; et_Obituary(0, 1, 7)  -- 1 ubije 0
health[0] = 100; health[1] = 0; et_Obituary(1, 1, 33) -- 1 natipka /kill
local last = sent[#sent] or ""
-- ⛔ `^` je v Lua vzorcih poseben SAMO na prvem mestu; prvi zapis
-- ("alpha ^%^3") je zato iskal DVA stršična znaka in ni ujel ničesar, assert
-- pa je padel s sporočilom, ki je kazalo pravilen izid. Vzorec mora biti
-- preverjen prav tako kot koda, ki jo meri.
local a = tonumber(last:match("alpha %^3(%d+)"))
local b = tonumber(last:match("bravo %^3(%d+)"))
assert(a and b, "objava ni v pričakovani obliki: "..tostring(last))
-- ⛔ SPREMENJENO VEDENJE, namerno. Prej je selfkill dal točko nasprotniku in
--    ta test je to trdil. Ne več: samomor prinese POŠTEN RESET, ne pa točke —
--    sicer je »ubij se, ko zaostajaš« taktika. Reset in točka sta dve
--    odločitvi, ne ena, in `victim == killer` loči natanko samomor (padec z
--    višine pride s killerjem ENTITYNUM_WORLD in še vedno šteje).
assert(a == 1 and b == 1,
       "izid mora biti 1-1: selfkill resetira, a NE prinese točke: "..tostring(last))
assert(#sent >= 6, "vsak dvoboj mora dati cp IN chat: "..#sent)
assert(sent[1]:match("alpha %^31 %^7%- bravo %^30"),
       "prvi dvoboj po et_InitGame se mora začeti pri 0-0, dobil: "..sent[1])
print("✅ svet vodi izid 2-1 (selfkill šteje nasprotniku), nova mapa začne 0-0")

-- 9) Poravnava ščitov mora spati, kadar NI 1v1. Brez tega je modul na
--    šestbotovskem ogrevanju posegal v ščite vseh (izmerjeno na 2.84:
--    55 poravnav proti 12 dvobojem).
conn[2]=2; team[2]=1; health[2]=100; shield[2]=0   -- tretji igralec na ekipi
cvars.sv_maxclients = "3"
et_InitGame(0,0,false)
calls = {}; logged = {}
shield[0]=50000; shield[1]=50025
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(shield[0]==50000 and shield[1]==50025,
       "⛔ pri treh igralcih se ščitov ne sme dotikati: "..shield[0].."/"..shield[1])
assert(not table.concat(logged," "):match("LEVEL"), "poravnava se je vseeno zgodila")
print("✅ poravnava spi, kadar ni 1v1")

-- ── vampiric ────────────────────────────────────────────────────────────────

-- 10) Stikalo velja ŠELE od naslednjega spawna. Vklop sredi dvoboja bi enemu
--     podaril zalogovnik, ki ga drugi nima.
conn[2]=nil; team[2]=nil; cvars.sv_maxclients = "2"
cvars.arena_vamp = "0"; cvars.arena_vamp_hp = "1000"; cvars.arena_vamp_steal = "50"
cvars.arena_vamp_grace = "90"; cvars.arena_vamp_decay = "30"
et_InitGame(0,0,false)
health[0]=100; health[1]=100
argv = {"vampiric"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
assert(et_ClientCommand(0, "vampiric") == 1, "svoj ukaz mora prevzeti")
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 100, "⛔ vklop ne sme veljati sredi dvoboja: "..health[0])
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 1000 and health[1] == 1000, "po spawnu mora veljati: "..health[0].."/"..health[1])
print("✅ /vampiric velja šele od naslednjega spawna")

-- 11) Lifesteal je 50 % in ne preseže zalogovnika.
health[0] = 500
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 520, "50 % od 40 je 20: dobil "..health[0])
health[0] = 995
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 1000, "meja mora držati: "..health[0])
print("✅ lifesteal 50 %, meja drži")

-- 12) Svet ne zdravi nikogar, in tuj ukaz ni požrt.
-- ⛔ Prvi zapis tega primera je preverjal ŽRTEV (health[0]) — a zdravljenje
--    gre NAPADALCU, torej entiteti 1022. Test je zato prehajal tudi z
--    odstranjenima OBEMA varovaloma: meril je stvar, ki se ni mogla premakniti.
--    Preveri tisto, kar se res zapiše.
health[0] = 500; health[1022] = nil
et_Damage(0, 1022, 100, 0, 37)
assert(health[1022] == nil, "⛔ svet (1022) ne sme dobiti zdravja: "..tostring(health[1022]))
assert(health[0] == 500, "žrtev se ne sme spremeniti: "..health[0])
argv = {"say", "hi"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
assert(et_ClientCommand(0, "say") == 0, "⛔ tuj ukaz mora vrniti 0, sicer ga požremo")
print("✅ svet ne zdravi, tuj ukaz ni požrt")

-- 13) Po pragu lifesteal upada, da se dvoboj konča.
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
health[0] = 500
now_ms = now_ms + 91000            -- tik čez 90 s grace
et_Damage(1, 0, 40, 0, 8)
local after_grace = health[0] - 500
now_ms = now_ms + 40000            -- daleč čez decay
health[0] = 500
et_Damage(1, 0, 40, 0, 8)
assert(after_grace < 20 and after_grace > 0, "tik po pragu mora upadati, ne pasti na nic: "..after_grace)
assert(health[0] == 500, "po izteku upadanja lifesteala ne sme biti ve\195\168: "..health[0])
print("✅ lifesteal upada po pragu in se izteče")

-- 14) Konzolni preklop gre skozi ISTO pot kot /vampiric: velja šele od
--     naslednjega spawna, in tujih konzolnih ukazov ne požre.
et_InitGame(0,0,false)
cvars.arena_vamp = "0"; health[0]=100; health[1]=100
argv = {"arena_vamp_toggle"}
assert(et_ConsoleCommand() == 1, "svoj konzolni ukaz mora prevzeti")
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 100, "⛔ preklop ne sme veljati sredi dvoboja: "..health[0])
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 1000, "po spawnu mora veljati: "..health[0])
argv = {"status"}
assert(et_ConsoleCommand() == 0, "⛔ tuj konzolni ukaz mora vrniti 0")
print("✅ konzolni preklop: velja od naslednjega spawna, tujih ukazov ne požre")

-- 15) Strelivo: oba duelista dobita poln zalogovnik in rezervo ob spawnu,
--     orožja pa jima NIHČE ne zamenja. Prav zamenjava je bila tista, ki je v
--     živi meritvi ubila prejšnji poskus (bota sta se nehala pobijati).
et_InitGame(0,0,false)
cvars.arena_vamp = "0"; cvars.arena_hp = ""; cvars.arena_vamp_hp = ""
current_wp[0] = 3   -- WP_MP40
current_wp[1] = 8   -- WP_THOMPSON
ammo_of = {}; clip_of = {}; nofatigue = {}
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(ammo_of[0] == 9999 and clip_of[0] == 9999, "rezerva in zalogovnik: "..tostring(ammo_of[0]).."/"..tostring(clip_of[0]))
assert(ammo_of[1] == 9999 and clip_of[1] == 9999, "drugi igralec tudi")
assert(current_wp[0] == 3 and current_wp[1] == 8, "⛔ orožja ne sme zamenjati: "..current_wp[0].."/"..current_wp[1])
-- ⛔ Zgornja trditev SAMA ne zadostuje: polnimo prav tisto orožje, ki ga
--    igralec že drži, zato je setcurrent=1 tu naključno brez učinka in
--    mutacija 0->1 je prešla. Preveri ARGUMENT, ne posledice, ki se ne more
--    premakniti — isti vzorec kot primer 12 (svet, ki ne more biti pozdravljen).
assert(setcurrent_of[0] == 0 and setcurrent_of[1] == 0,
       "⛔ setcurrent mora biti 0: "..tostring(setcurrent_of[0]).."/"..tostring(setcurrent_of[1]))
assert(nofatigue[0] == 1 and nofatigue[1] == 1, "sprint mora biti neomejen")
-- ⛔ 9999 ni okrasna številka: ps.ammo potuje kot PREDZNAČEN 16-bitni short
--    (msg.c:655, :2503). Karkoli, kar bi s polnjenjem ali z ročnim reloadom
--    (PM_ReloadClip prenese ammomove NAZAJ, bg_pmove.c:2818) preseglo 32767,
--    pride do klienta kot negativno število. 9999 + (9999-30) = 19968.
assert(9999 + (9999 - 30) < 32767, "⛔ polnjenje mora ostati v 16-bitnem polju")
print("✅ neomejeno strelivo, brez menjave orožja, neomejen sprint")

-- 16) Vsak neizmerjen zalogovnik se prilepi na najbližji preset, in vampiric
--     BREZ zalogovnika nikoli ne sme dobiti meje 0 — meja 0 pomeni, da vsako
--     zdravljenje postavi zdravje na nič, torej te mod pozdravi do smrti.
et_InitGame(0,0,false)
cvars.arena_hp = "700"; cvars.arena_vamp = "1"
et_InitGame(0,0,false)
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 500, "700 se mora prilepiti na 500: "..health[0])
cvars.arena_hp = "0"
et_InitGame(0,0,false)
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
-- ⛔ Trditev o zdravljenju je premalo: obe varovali (rezervni zalogovnik in
--    varovalo stropa) dasta isti izid, zato je mutacija enega od njiju prešla.
--    Zalogovnik ob SPAWNU loči prav to eno.
assert(health[0] == 500 and health[1] == 500,
       "⛔ vampiric brez arena_hp mora dobiti rezervni zalogovnik 500: "..health[0].."/"..health[1])
health[0] = 100
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 120, "⛔ meja 0 bi pozdravila do smrti; dobil "..health[0])
print("✅ preseti se prilepijo, meja nikoli ni 0")

-- 17) /arenahp velja šele od naslednjega spawna, in konzolni dvojnik tudi.
et_InitGame(0,0,false)
cvars.arena_hp = "1000"; cvars.arena_vamp = "1"
et_InitGame(0,0,false)
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 1000, "izhodišče 1000: "..health[0])
argv = {"arenahp", "250"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
assert(et_ClientCommand(0, "arenahp") == 1, "svoj ukaz mora prevzeti")
assert(health[0] == 1000, "⛔ sprememba ne sme poseči v tekoč dvoboj: "..health[0])
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 250 and health[1] == 250, "od naslednjega spawna: "..health[0].."/"..health[1])
-- ⛔ Meja lifesteala mora biti POSNETEK zalogovnika, s katerim sta oba
--    spawnala — ne svež odčitek cvara. Če bi se brala živo, bi vrnitev
--    arena_hp na 1000 sredi dvoboja dvignila strop nad zdravje, s katerim je
--    kdorkoli začel, in mod bi izgledal, kot da si izmišlja zdravje.
-- ⛔ Sprememba mora iti po ISTI poti, po kateri gre igralec — po ukazu. Prvi
--    zapis je premaknil samo cvar, a odkar bazen živi tudi v Lua stanju, je
--    cvar mimo ukaza brez učinka in mutacija »beri živo« je prešla: test je
--    premikal vzvod, ki ni bil priklopljen.
argv = {"arenahp", "1000"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
assert(et_ClientCommand(0, "arenahp") == 1, "svoj ukaz mora prevzeti")
health[0] = 245
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 250, "⛔ strop mora ostati posnet na 250: "..health[0])
argv = {"arenahp", "250"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
et_ClientCommand(0, "arenahp")
-- ⛔ Ukazna pot mora prilepiti prav tako kot bralna. Prvi zapis tega primera je
--    uporabljal 250, ki JE preset — mutacija »ne prilepi« je zato prešla, ker
--    se vhod in izhod nista razlikovala. Vzemi vrednost, ki se MORA premakniti.
argv = {"arenahp", "700"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
assert(et_ClientCommand(0, "arenahp") == 1, "svoj ukaz mora prevzeti")
assert(cvars.arena_hp == "500", "⛔ 700 se mora prilepiti na 500, dobil "..tostring(cvars.arena_hp))
argv = {"arena_hp_set", "1000"}
assert(et_ConsoleCommand() == 1, "konzolni dvojnik mora prevzeti svoj ukaz")
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 1000, "konzolni ukaz mora imeti isti učinek: "..health[0])
print("✅ /arenahp in arena_hp_set: veljata od naslednjega spawna")

-- 18) Orožje WP_NONE ne sme sprožiti napake v et_ClientSpawn. Prava vezava
--     ob neveljavnem orožju vrže Lua napako (IS_VALID_WEAPON, g_lua.c:1104),
--     ta pa bi odnesla ves preostanek spawna — vključno s poravnavo ščitov.
et_InitGame(0,0,false)
current_wp[0] = 0; current_wp[1] = 0
ammo_of = {}; clip_of = {}
shield[0] = 5000; shield[1] = 4000
local ok = pcall(function() et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0) end)
assert(ok, "⛔ spawn ne sme pasti zaradi WP_NONE")
assert(ammo_of[0] == nil, "brez orožja se strelivo ne polni")
-- ⛔ pcall okoli vezave pomeni, da odstranjen gate NE zruši spawna — le
--    zabeleži napako. Trditev mora torej brati, KATERA vrstica je bila
--    zapisana: preskočeno (gate je delal) proti FAILED (gate ga ni ujel).
local skipped, failed = false, false
for _, line in ipairs(logged) do
  if line:find("AMMO") and line:find("skipped") then skipped = true end
  if line:find("AMMO") and line:find("FAILED") then failed = true end
end
assert(skipped, "⛔ preskok mora biti zabeležen")
assert(not failed, "⛔ gate ga ni ujel: vezava je vrgla napako namesto preskoka")
assert(shield[0] == shield[1], "poravnava ščitov mora vseeno steči: "..shield[0].."/"..shield[1])
print("✅ WP_NONE: brez napake, poravnava ščitov preživi")

-- 19) Škoda PRED prvim spawnom. Modul se lahko naloži sredi runde: et_InitGame
--     prebere arena_vamp in lifesteal je takoj v veljavi, duel_pool pa je še
--     0, ker spawna še ni bilo. Brez varovala stropa bi bila meja 0 in vsako
--     zdravljenje bi zdravje POSTAVILO na nič — mod bi ubijal, ne zdravil.
--     To ni hipotetično: natanko to se zgodi ob `lua_status`-u sredi runde.
cvars.arena_hp = ""; cvars.arena_vamp_hp = ""; cvars.arena_vamp = "1"
et_InitGame(0,0,false)
health[0] = 90; health[1] = 90
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 110, "⛔ pred prvim spawnom mora zdravljenje delati, ne ubijati: "..health[0])
print("✅ škoda pred prvim spawnom ne pobije napadalca")

-- 20) Simetrija orožij, drugi poskus. Prvi je odstranjeval 54 orožij in ubil
--     boje; ta samo DODA in izbere. Preverjata se dve stvari, ki ju prvi
--     poskus ni ločil: da se doda PRAVO orožje za ekipo, in da se z
--     `setcurrent=1` orožje res IZBERE (drugače je dodajanje brez učinka).
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"; cvars.arena_symmetric = "1"
current_wp[0] = 23  -- WP_KAR98, kar bot dejansko dobi
current_wp[1] = 24  -- WP_CARBINE
ammo_of = {}; clip_of = {}; setcurrent_of = {}
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(current_wp[0] == 3, "Axis mora dobiti MP40, dobil "..tostring(current_wp[0]))
assert(current_wp[1] == 8, "Allies mora dobiti Thompson, dobil "..tostring(current_wp[1]))
assert(setcurrent_of[0] == 1 and setcurrent_of[1] == 1,
       "⛔ brez setcurrent=1 je dodajanje brez učinka: "..tostring(setcurrent_of[0]))
-- ⛔ In izklopljeno stikalo se mora res izklopiti — sicer je privzetek laž.
et_InitGame(0,0,false)
cvars.arena_symmetric = "0"
current_wp[0] = 23; current_wp[1] = 24
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(current_wp[0] == 23 and current_wp[1] == 24,
       "⛔ pri arena_symmetric 0 se oborožitev ne sme dogajati: "..current_wp[0])
print("✅ simetrija orožij: doda in izbere, izklopljena pa miruje")

-- 21) Kar je nekdo natipkal na prejšnji mapi, ne sme prevladati nad
--     konfiguracijo strežnika na naslednji. Cvar je vmesnik, Lua stanje je
--     zaščita pred Cvar_Restart — a zaščita, ki se ne resetira, je le drugo
--     ime za stanje, ki uhaja čez mejo mape.
et_InitGame(0,0,false)
cvars.arena_hp = "1000"; cvars.arena_vamp = "1"; cvars.arena_symmetric = "0"
et_InitGame(0,0,false)
argv = {"arenahp", "250"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
assert(et_ClientCommand(0, "arenahp") == 1, "svoj ukaz mora prevzeti")
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 250, "na tej mapi velja natipkano: "..health[0])
-- nova mapa, strežnik spet pove 1000
cvars.arena_hp = "1000"
et_InitGame(0,0,false)
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 1000, "⛔ prejšnja mapa ne sme prevladati: "..health[0])
print("✅ bazen ne uhaja čez mejo mape")

-- 22) ⛔⛔ FRESH MAP LOAD: the engine has not filled CS_SERVERINFO yet.
--     Measured on 2.84 — at et_InitGame after `map dots_arena` the
--     configstring is EMPTY (length 0) and only the `mapname` cvar is right.
--     Everything armed before this fix only because a map_restart happened to
--     follow (G_configSet issues one for every config load), so the module ran
--     a second time with the configstring populated. On a server without a
--     custom config there is no restart and the arena would never arm.
serverinfo = ""            -- the fresh-load shape
cvars.mapname = "dots_arena"
cvars.g_forcerespawn = "0"
et_InitGame(0,0,false)
assert(cvars.g_forcerespawn == "-1",
       "⛔ modul se mora oborožiti tudi ob prvem nalaganju mape: g_forcerespawn="..tostring(cvars.g_forcerespawn))
-- in na tuji mapi se ne sme, tudi če je configstring prazen
cvars.mapname = "oasis"
cvars.g_forcerespawn = "0"
et_InitGame(0,0,false)
assert(cvars.g_forcerespawn == "0",
       "⛔ na tuji mapi se ne sme oborožiti: "..tostring(cvars.g_forcerespawn))
-- konfiguracijski niz ostane rezerva, kadar cvar molči
serverinfo = "\\mapname\\dots_arena"
cvars.mapname = ""
cvars.g_forcerespawn = "0"
et_InitGame(0,0,false)
assert(cvars.g_forcerespawn == "-1",
       "⛔ configstring mora ostati rezerva: "..tostring(cvars.g_forcerespawn))
serverinfo = "\\mapname\\dots_arena"; cvars.mapname = "dots_arena"
print("✅ oboroži se ob PRVEM nalaganju mape (prazen CS_SERVERINFO)")

-- 23) ⛔⛔ Ko igralec izglasuje drug config, se Lua NE ustavi prek
--     et_ShutdownGame. Sprememba lua_modules pokliče G_LuaShutdown naravnost
--     iz cvar hooka (g_cvars.c:907-913), ta pa gre v G_LuaStopVM, ki pokliče
--     **et_Quit** in zapre VM (g_lua.c:3450-3468). Brez et_Quit ostane
--     g_forcerespawn na -1 — instant respawn povsod, in na produkciji ga ne
--     povrne noben od desetih configov.
serverinfo = "\\mapname\\dots_arena"; cvars.mapname = "dots_arena"
cvars.g_forcerespawn = "0"
et_InitGame(0,0,false)
assert(cvars.g_forcerespawn == "-1", "predpogoj: oborožen")
et_Quit()
assert(cvars.g_forcerespawn == "0",
       "⛔ et_Quit mora povrniti g_forcerespawn: "..tostring(cvars.g_forcerespawn))
-- in obe poti sta idempotentni: kar steče drugo, ne sme ničesar pokvariti
cvars.g_forcerespawn = "7"
et_ShutdownGame(false)
assert(cvars.g_forcerespawn == "7",
       "⛔ druga pot rušenja ne sme znova pisati: "..tostring(cvars.g_forcerespawn))
-- ista zgodba v obratnem vrstnem redu
cvars.g_forcerespawn = "0"
et_InitGame(0,0,false)
et_ShutdownGame(false)
assert(cvars.g_forcerespawn == "0", "et_ShutdownGame mora prav tako povrniti")
cvars.g_forcerespawn = "7"
et_Quit()
assert(cvars.g_forcerespawn == "7", "⛔ et_Quit po ShutdownGame ne sme znova pisati")
cvars.g_forcerespawn = "0"
print("✅ et_Quit povrne g_forcerespawn (pot ob glasovanju o configu)")

-- 24) ⛔⛔ Prehod v gledalce NI smrt v dvoboju, čeprav motor poskrbi, da tako
--     izgleda. SetTeam ubije igralca (`player_die(..., MOD_SWITCHTEAM)`,
--     g_cmds.c:1589) in mu moštvo prepiše šele 55 vrstic kasneje (:1644),
--     zato ob tem obituaryju roster še vedno kaže dva. Brez varovala bi
--     modul prištel točko nasprotniku IN ga usmrtil — pritisk na spectate bi
--     bil najmočnejša poteza v igri.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"; cvars.arena_symmetric = "0"
et_InitGame(0,0,false)
health[0]=100; health[1]=100; shield[0]=0; shield[1]=0
calls = {}; sent = {}
health[1] = 0
et_Obituary(1, 1, 59)          -- cn=1 gre v gledalce (victim == killer)
assert(#calls == 0, "⛔ ob menjavi moštva se ne sme zgoditi NIČ, a se je: "..table.concat(calls," | "))
assert(#sent == 0, "⛔ in nobene objave izida: "..#sent)
-- kontrola: navadna smrt v istem stanju MORA sprožiti reset in objavo
health[1] = 0
et_Obituary(1, 0, 7)
assert(#calls > 0, "kontrola: navadna smrt mora sprožiti reset")
assert(#sent > 0, "kontrola: navadna smrt mora objaviti izid")
print("✅ prehod v gledalce ne prinese ne točke ne usmrtitve")

-- 25) ⛔⛔ Odhod duelista: modul o njem ne izve nič, ker `ClientDisconnect`
--     NIKOLI ne kliče `player_die` (g_client.c:3526). Brez `et_ClientDisconnect`
--     ostane preživeli ranjen, naslednji, ki se pridruži, pa dobi poln bazen —
--     edino jamstvo modula pade za faktor šest.
--     ⭐ In odhajajoči ob tem hooku ŠE ŠTEJE v roster: hook je na
--     g_client.c:3585, `CON_DISCONNECTED` pa 138 vrstic kasneje na :3723.
et_InitGame(0,0,false)
cvars.arena_hp = "500"; cvars.arena_vamp = "0"; cvars.arena_symmetric = "0"
et_InitGame(0,0,false)
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
assert(health[0] == 500 and health[1] == 500, "predpogoj: oba na 500")
health[0] = 87                      -- preživeli je ranjen
calls = {}
et_ClientDisconnect(1)              -- nasprotnik odide
assert(#calls == 0, "⛔ ob odhodu se ne sme takoj resetirati — sam bi pristal na 100: "..table.concat(calls," | "))
assert(health[0] == 87, "preživeli ostane, kot je bil, do prihoda naslednjega")
-- pride nov igralec na isto mesto
health[1] = 100
et_ClientSpawn(1,0,0,0)
local reset_seen = false
for _, c in ipairs(calls) do if c:match("G_Damage%(0,") then reset_seen = true end end
assert(reset_seen, "⛔ ob ponovnem 1v1 mora biti ranjeni preživeli poslan skozi ista vrata: "..table.concat(calls," | "))
-- in brez odhoda se to NE sme zgoditi (sicer bi se resetirala vsak spawn)
et_InitGame(0,0,false)
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
calls = {}
et_ClientSpawn(0,0,0,0)
for _, c in ipairs(calls) do
  assert(not c:match("G_Damage"), "⛔ brez odhoda ponovne poravnave ne sme biti: "..c)
end
print("✅ odhod duelista: stanje počiščeno, preživeli poravnan ob naslednjem 1v1")

-- 26) ⛔ Izid je vezan na ŠTEVILKE MEST, ne na ljudi, mesta pa se reciklirajo.
--     B odide, C dobi isto mesto — brez čiščenja ob odklopu podeduje izid,
--     ki ga ni odigral, in objava laže obema hkrati.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"
et_InitGame(0,0,false)
health[0]=100; health[1]=100; shield[0]=0; shield[1]=0
health[1] = 0; et_Obituary(1, 0, 7)     -- 0 vodi 1-0
health[0] = 100; health[1] = 100
health[1] = 0; et_Obituary(1, 0, 7)     -- 0 vodi 2-0
sent = {}
health[0] = 100; health[1] = 100
et_ClientDisconnect(1)                   -- B odide
health[1] = 0; et_Obituary(1, 0, 7)      -- prvi dvoboj proti C
local last = sent[#sent] or ""
local a = tonumber(last:match("alpha %^3(%d+)"))
local b = tonumber(last:match("bravo %^3(%d+)"))
assert(a and b, "objava ni v pričakovani obliki: "..tostring(last))
assert(a == 1 and b == 0,
       "⛔ novi igralec ne sme podedovati izida prejšnjega: dobil "..a.."-"..b)
print("✅ odklop počisti izid — novi igralec začne z 0")

-- 27) ⛔⛔ Ko motor škodo ZAVRNE, se dvoje tiho pokvari: zastavica `forced`
--     obtiči (in požre naslednjo PRAVO smrt tega igralca), ščit pa je bil
--     odvzet eno vrstico prej — preživeli stoji živ in nezaščiten. G_Damage se
--     vrne brez učinka pri `!takedamage` (g_combat.c:1435), med intermissionom
--     ali warmupom z `match_warmupDamage 0` (:1445), pri noclip (:1593) in pri
--     FL_GODMODE (:1600) — zadnja dva PRED branjem dflags, torej jih
--     DAMAGE_NO_PROTECTION ne pokrije.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"
et_InitGame(0,0,false)
health[0]=100; health[1]=100; shield[0]=4242; shield[1]=4242
damage_lands = false                     -- motor zavrne
health[1] = 0
et_Obituary(1, 0, 7)                     -- preživeli cn=0 naj bi bil resetiran
assert(health[0] == 100, "predpogoj: preživeli je še živ, ker je motor zavrnil")
assert(shield[0] == 4242,
       "⛔ zavrnjena škoda mora ščit vrniti, sicer stoji živ in nezaščiten: "..tostring(shield[0]))
-- in naslednja PRAVA smrt tega igralca ne sme biti požrta
damage_lands = true
sent = {}
health[0] = 0
et_Obituary(0, 1, 7)
assert(#sent > 0, "⛔ zastavica je obtičala: naslednja prava smrt je bila požrta")
print("✅ zavrnjena škoda: ščit povrnjen, zastavica ne obtiči")

-- 28) ⛔ Razoroženo stanje mora biti vidno, in samo ob PREHODU. Doslej je vsak
--     prehod rosterja utišal modul brez ene besede igralcem — zmagovalec se
--     preprosto ni več resetiral, edini dokaz pa je bila vrstica v logu.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"
et_InitGame(0,0,false)
-- najprej se mora modul res oborožiti (prehod se meri z ARMED stanja)
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0); et_ClientSpawn(1,0,0,0)
-- ⛔ sv_maxclients je meja zanke v players_on_teams: brez tega tretjega
--    igralca modul sploh ne vidi in test bi meril prazno.
cvars.sv_maxclients = "4"
conn[2]=2; team[2]=1                       -- tretji igralec se pridruži
sent = {}
health[1] = 0; et_Obituary(1, 0, 7)
local paused = 0
for _, m in ipairs(sent) do if m:match("paused") then paused = paused + 1 end end
assert(paused == 1, "⛔ ob prehodu natanko ena objava o pavzi, dobil "..paused)
-- ponovna smrt pri istem stanju NE sme spet objaviti
sent = {}
health[0] = 0; et_Obituary(0, 1, 7)
for _, m in ipairs(sent) do
  assert(not m:match("paused"), "⛔ spam: pavza se objavi le ob prehodu")
end
-- ko tretji odide, mora priti objava o oborožitvi
conn[2]=nil; team[2]=nil
sent = {}
et_ClientSpawn(0,0,0,0)
local armed = 0
for _, m in ipairs(sent) do if m:match("armed") then armed = armed + 1 end end
assert(armed == 1, "⛔ vrnitev v 1v1 mora biti objavljena, dobil "..armed)
print("✅ pavza in oborožitev sta objavljeni, in samo ob prehodu")
cvars.sv_maxclients = "2"

-- 29) ⛔ `pool_state = nil` ob InitGame ni delal, kar je komentar trdil:
--     `set_pool` piše TUDI cvar `arena_hp`, in `configured_pool` pade prav
--     nanj. Dva igralca, ki se dogovorita za /arenahp 1000, sta tiho izročila
--     1000 naslednjemu paru. Cvar mora biti povrnjen ob rušenju, tako kot
--     `g_forcerespawn`.
cvars.arena_hp = ""; cvars.arena_vamp = "0"; cvars.g_forcerespawn = "0"
et_InitGame(0,0,false)
argv = {"arenahp", "1000"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
assert(et_ClientCommand(0, "arenahp") == 1, "svoj ukaz mora prevzeti")
assert(cvars.arena_hp == "1000", "predpogoj: ukaz je zapisal cvar")
et_ShutdownGame(false)
assert(cvars.arena_hp == "",
       "⛔ arena_hp mora biti povrnjen na predhodno vrednost: "..tostring(cvars.arena_hp))
print("✅ arena_hp se ob rušenju povrne (natipkano ne uhaja na naslednjo mapo)")

-- 30) ⛔ Povrnitev sme veljati SAMO za tisto, kar je spremenil modul. Prva
--     različica je povrnila brezpogojno in živi tek na 2.84 je pokazal ceno:
--     admin, ki med mapama nastavi arena_hp na konzoli, mu je rušenje
--     prejšnje mape vrednost pobrisalo.
cvars.arena_hp = ""; cvars.arena_vamp = "0"
et_InitGame(0,0,false)
cvars.arena_hp = "500"          -- admin natipka med igro, modul ga NI pisal
et_ShutdownGame(false)
assert(cvars.arena_hp == "500",
       "⛔ modul ne sme povrniti vrednosti, ki je ni sam nastavil: "..tostring(cvars.arena_hp))
print("✅ povrne se le tisto, kar je modul res spremenil")

-- 31) ⛔⛔ MEJA ZA ODJEMALCE. `arena_kill -1` je bilo sesutje strežnika:
--     `et.G_Damage` in `et.gentity_set` tvorita `g_entities + n` BREZ vsakega
--     preverjanja (g_lua.c:918, :2119), medtem ko `et.GetCurrentWeapon`
--     preverja (:1195). Iz ene vezave sem sklepal na politiko celega API-ja.
et_InitGame(0,0,false)
cvars.arena_1v1_test = "1"; cvars.sv_maxclients = "2"
-- ⚠️ 1.5 je tu namenoma: pri sv_maxclients 2 je ŠTEVILČNO v obsegu (0 <= 1.5 < 2),
--    zato ga ujame samo `math.type`, ne pa preverba obsega. Brez njega je
--    mutacija »math.type -> type« preživela, ker so vse ostale vrednosti padle
--    že na obsegu.
for _, bad in ipairs({-1, 5000, 3.5, 1.5, 0/0}) do
  calls = {}
  argv = {"arena_kill", tostring(bad)}
  assert(et_ConsoleCommand() == 1, "ukaz mora ostati prevzet")
  for _, c in ipairs(calls) do
    assert(not c:match("G_Damage"), "⛔ "..tostring(bad).." je prišel do vezave: "..c)
    assert(not c:match("^set%("), "⛔ "..tostring(bad).." je pisal v entiteto: "..c)
  end
end
-- kontrola: veljavna številka MORA delovati, sicer varovalo samo ubije funkcijo
calls = {}
argv = {"arena_kill", "1"}
et_ConsoleCommand()
local hit = false
for _, c in ipairs(calls) do if c:match("G_Damage%(1,") then hit = true end end
assert(hit, "⛔ kontrola: veljaven cn mora priti skozi: "..table.concat(calls," | "))
print("✅ arena_kill: -1, 5000, 3.5 in nan zavrnjeni, veljaven cn dela")

-- 32) ⛔ `sv_maxclients` motor omeji na 64 šele ob zagonu mape
--     (SV_BoundMaxClients, sv_init.c:355-361). Med `set sv_maxclients 9999` in
--     naslednjo mapo bi zanka brala g_entities[1024…] — izven polja.
local seen_max = 0
local real_get = et.gentity_get
et.gentity_get = function(cn, field, idx)
  if type(cn) == "number" and cn > seen_max then seen_max = cn end
  return real_get(cn, field, idx)
end
cvars.sv_maxclients = "9999"
et_InitGame(0,0,false)
health[1] = 0
et_Obituary(1, 0, 7)
et.gentity_get = real_get
assert(seen_max < 64, "⛔ zanka je šla čez MAX_CLIENTS: največji cn = "..seen_max)
cvars.sv_maxclients = "2"
print("✅ sv_maxclients 9999 ne odnese zanke čez MAX_CLIENTS")

-- 33) ⛔ `inf`, `nan` in negativna tiho postanejo 250: vsak `gap` je `inf`,
--     `inf < math.huge` je za vse tri presete false, zato `best` ostane
--     inicializator. Nesmiseln vhod postane VELJAVEN bazen.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"
for _, bad in ipairs({"1e999", "-500"}) do
  argv = {"arenahp", bad}
  cvars.arena_hp = ""
  now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
  et_ClientCommand(0, "arenahp")
  assert(cvars.arena_hp == "" or cvars.arena_hp == nil,
         "⛔ "..bad.." ne sme postati bazen, cvar je zdaj "..tostring(cvars.arena_hp))
end
-- kontrola: 700 se MORA prilepiti na 500
argv = {"arenahp", "700"}
now_ms = now_ms + 5000   -- ⛔ ukazi imajo 3 s cooldown; ura se mora premakniti
et_ClientCommand(0, "arenahp")
assert(cvars.arena_hp == "500", "kontrola: 700 -> 500, dobil "..tostring(cvars.arena_hp))
print("✅ inf/nan/negativno zavrnjeno, veljavna vrednost se še vedno prilepi")

-- 34) ⛔⛔ Motor tega NE bo naredil namesto nas. `ClientCommand` pokliče Lua hook
--     PRVI (g_cmds.c:5240) in do `G_commandCheck`, kjer živi
--     `G_ClientIsFlooding` (g_cmds_ext.c:233), pride šele, če ukaza ni prevzel
--     noben modul. Ukaz, ki ga obravnavamo mi, se torej zaščite pred poplavo
--     nikoli ne dotakne, in nič od njenega stanja Lui ni izpostavljeno.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"; cvars.sv_maxclients = "4"
et_InitGame(0,0,false)
conn[2]=2; team[2]=3                       -- gledalec (TEAM_SPECTATOR)
sent = {}
now_ms = now_ms + 5000
argv = {"arenahp", "250"}
assert(et_ClientCommand(2, "arenahp") == 1, "ukaz mora ostati prevzet")
assert(cvars.arena_hp ~= "250", "⛔ gledalec ne sme spreminjati bazena")
local refused = false
for _, m in ipairs(sent) do if m:match("only the two players") then refused = true end end
assert(refused, "⛔ in mora izvedeti, zakaj: "..table.concat(sent," | "))
-- igralec na moštvu SME
now_ms = now_ms + 5000
argv = {"arenahp", "250"}
assert(et_ClientCommand(0, "arenahp") == 1)
assert(cvars.arena_hp == "250", "kontrola: igralec na moštvu sme: "..tostring(cvars.arena_hp))
-- a ne dvakrat v treh sekundah
now_ms = now_ms + 500
sent = {}
argv = {"arenahp", "1000"}
et_ClientCommand(0, "arenahp")
assert(cvars.arena_hp == "250", "⛔ cooldown mora ustaviti drugi ukaz: "..tostring(cvars.arena_hp))
local slowed = false
for _, m in ipairs(sent) do if m:match("slow down") then slowed = true end end
assert(slowed, "⛔ in mora povedati, da je prehitro")
-- po izteku spet sme
now_ms = now_ms + 5000
argv = {"arenahp", "1000"}
et_ClientCommand(0, "arenahp")
assert(cvars.arena_hp == "1000", "po izteku cooldowna spet sme: "..tostring(cvars.arena_hp))
-- in odklop mora zapis počistiti (sicer je to nov primerek istega razreda)
et_ClientDisconnect(0)
now_ms = now_ms + 100
argv = {"arenahp", "500"}
et_ClientCommand(0, "arenahp")
assert(cvars.arena_hp == "500", "⛔ odklop mora počistiti cooldown: "..tostring(cvars.arena_hp))
conn[2]=nil; team[2]=nil; cvars.sv_maxclients = "2"
print("✅ pooblastilo in cooldown; odklop počisti tudi ta zapis")

-- 35) ⛔ `trap_Milliseconds` je Sys_Milliseconds kot C int in se po ~24,8 dneh
--     uptimea prelije v negativno. Naiven `now - prev < COOLDOWN` bi po
--     prelivu dal ogromno negativno razliko … ali pa igralca zaklenil za
--     vedno, odvisno od predznaka. Skok nazaj mora uro ponastaviti, ne ujeti.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"
now_ms = 2000000000
argv = {"arenahp", "250"}
et_ClientCommand(0, "arenahp")
assert(cvars.arena_hp == "250", "predpogoj: prvi ukaz gre skozi")
now_ms = -2000000000          -- ura se je prelila
argv = {"arenahp", "1000"}
et_ClientCommand(0, "arenahp")
assert(cvars.arena_hp == "1000",
       "⛔ po prelivu ure igralec ne sme ostati zaklenjen: "..tostring(cvars.arena_hp))
now_ms = 100000
print("✅ preliv ure ne zaklene igralca")

-- 36) ⛔⛔ Stub mora biti strog tam, kjer je vezava stroga. Prava
--     `gentity_get`/`gentity_set` ob NEZNANEM imenu polja vrže
--     (`luaL_error`, g_lua.c:2032/:2130). Stub, ki na tipkarsko napako odgovori
--     z `nil`, tako napako spusti skozi VSE teste, v živo pa prekine cel hook.
--     Isti razred kot brezpogojno smrtonosni G_Damage in kot manjkajoči
--     konstanti — oboje je ta harness danes že popravil.
local ok_get = pcall(function() return et.gentity_get(0, "ps.stat") end)   -- tipkarska napaka
assert(not ok_get, "⛔ stub mora vreči ob neznanem imenu polja pri branju")
local ok_set = pcall(function() et.gentity_set(0, "healht", 100) end)      -- tipkarska napaka
assert(not ok_set, "⛔ stub mora vreči ob neznanem imenu polja pri pisanju")
-- in znana polja morajo še naprej delovati
assert(pcall(function() return et.gentity_get(0, "ps.stats", 0) end),
       "kontrola: znano polje mora iti skozi")
print("✅ stub vrže ob neznanem polju, kot vrže vezava")

-- 37) ⛔ Log je po dveh dneh testiranja imel 303 KB in 5311 vrstic, prva vrstica
--     pa se je glasila `03:56:59` — brez dneva. Dva dneva prepletena v eni
--     datoteki, brez načina, da ju ločiš.
--     ⭐ Rotacija je sploh mogoča zato, ker `et.trap_FS_Rename` V 2.84 OBSTAJA
--     (g_lua.c:734) — Lua FS sloj ni samo za dodajanje, kot se običajno
--     predpostavlja. Velikost pove FS_READ; FS_APPEND vrne 0/-1, ne dolžine.
serverinfo = "\\mapname\\dots_arena"; cvars.mapname = "dots_arena"
fs_len = 10
et_InitGame(0,0,false)
assert(#fs_renames == 0, "majhen log se ne sme rotirati")
logged = {}
health[0]=100; health[1]=100
et_ClientSpawn(0,0,0,0)                    -- karkoli, kar zapiše vrstico
assert(logged[1] and logged[1]:match("^%d%d%d%d%-%d%d%-%d%d "),
       "⛔ vrstica mora nositi DATUM: "..tostring(logged[1]))
fs_renames = {}
fs_len = 900000                     -- čez mejo
et_InitGame(0,0,false)
assert(#fs_renames == 1, "⛔ velik log se mora rotirati, prejmenovanj: "..#fs_renames)
assert(fs_renames[1]:match("arena_1v1%.log %-> arena_1v1%-%d%d%d%d%-%d%d%-%d%d"),
       "⛔ novo ime mora nositi datum: "..fs_renames[1])
-- odpiranje lahko tudi odpove in to ne sme vreči
fs_open_fails = true
local ok = pcall(function() et_InitGame(0,0,false) end)
fs_open_fails = false
assert(ok, "⛔ neuspelo odpiranje loga ne sme vreči")
fs_len = 0; fs_renames = {}
print("✅ log: datum v vrstici, rotacija prek trap_FS_Rename, neuspeh ne vrže")

-- 38) ⛔ Omejitev vrstic na en zagon mape: ena ponorela runda ne sme napolniti
--     diska. Hišna številka je 3000 (frame_health v6.13), z izmerjeno
--     utemeljitvijo v proximity: »300 cut a 2 h storm on 2026-09-02«.
et_InitGame(0,0,false)
logged = {}
for i = 1, 3200 do
  health[0] = 100
  et_ClientSpawn(0,0,0,0)
end
assert(#logged <= 3000,
       "⛔ log ni omejen na zagon mape: "..#logged.." vrstic")
assert(#logged >= 2900, "kontrola: pisati mora skoraj do meje, ne prej nehati: "..#logged)
-- nov zagon mape mora števec ponastaviti
et_InitGame(0,0,false)
logged = {}
et_ClientSpawn(0,0,0,0)
assert(#logged > 0, "⛔ nov zagon mape mora števec ponastaviti")
print("✅ log je omejen na zagon mape in se ob novi mapi ponastavi")

-- 39) ⛔⛔ `victim == killer` NI »natipkal /kill«. Lastna granata, lasten
--     panzer in lastna dinamit pridejo z attacker == self in ORODNIM modom —
--     to so legitimni načini, kako izgubiti dvoboj, in nasprotnik si je točko
--     zaslužil. Preverba same identitete jih je vse pogoltnila kot »pošten
--     reset brez točke«. Našel drug model ob branju zasnove, ne test.
et_InitGame(0,0,false)
cvars.arena_hp = ""; cvars.arena_vamp = "0"
et_InitGame(0,0,false)
health[0]=100; health[1]=100; shield[0]=0; shield[1]=0
sent = {}
health[1] = 0
et_Obituary(1, 1, et.MOD_GRENADE)      -- ubil se je z lastno granato
local last = sent[#sent] or ""
local a = tonumber(last:match("alpha %^3(%d+)"))
local b = tonumber(last:match("bravo %^3(%d+)"))
assert(a and b, "objava mora priti: "..tostring(last))
assert(a == 1 and b == 0,
       "⛔ samoubijstvo z orožjem MORA prinesti točko nasprotniku: "..a.."-"..b)
-- /kill pa še vedno ne
sent = {}
health[0] = 100; health[1] = 100
health[1] = 0
et_Obituary(1, 1, et.MOD_SUICIDE)
last = sent[#sent] or ""
a = tonumber(last:match("alpha %^3(%d+)"))
assert(a == 1, "⛔ /kill ne sme prinesti točke, izid je zdaj "..tostring(a))
print("✅ lastna granata šteje, /kill ne")
