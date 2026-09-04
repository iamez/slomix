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
local serverinfo = "\\mapname\\dots_arena"
et = {
  TEAM_AXIS=1, TEAM_ALLIES=2, STAT_HEALTH=0, CS_SERVERINFO=0, PW_INVULNERABLE=1,
  MOD_SUICIDE=37, FS_APPEND=2, PW_NOFATIGUE=4,
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
  trap_FS_FOpenFile=function() return 7, 0 end,
  trap_FS_Write=function(line) logged[#logged+1]=line:gsub("\n","") end,
  trap_FS_FCloseFile=function() end,
  gentity_get=function(cn, field, idx)
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
    if field=="ps.powerups" and idx==1 then shield[cn]=val end
    if field=="ps.powerups" and idx==4 then nofatigue[cn]=val end
    if field=="health" then health[cn]=idx end
    if field=="ps.stats" and idx==0 then health[cn]=val end
    calls[#calls+1]=("set(%d,%s,%s,%s)"):format(cn, field, tostring(idx), tostring(val))
  end,
  G_Damage=function(t,i,a,d,f,m)
    calls[#calls+1]=("G_Damage(%d,%d,%d,%d,0x%x,%d)"):format(t,i,a,d,f,m)
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
  if c:match("^G_Damage%(0,1022,1022,1000,0x20,37%)$") then idmg = i end
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
health[0] = 100; health[1] = 0; et_Obituary(1, 1, 37) -- 1 se ubije sam
local last = sent[#sent] or ""
-- ⛔ `^` je v Lua vzorcih poseben SAMO na prvem mestu; prvi zapis
-- ("alpha ^%^3") je zato iskal DVA stršična znaka in ni ujel ničesar, assert
-- pa je padel s sporočilom, ki je kazalo pravilen izid. Vzorec mora biti
-- preverjen prav tako kot koda, ki jo meri.
local a = tonumber(last:match("alpha %^3(%d+)"))
local b = tonumber(last:match("bravo %^3(%d+)"))
assert(a and b, "objava ni v pričakovani obliki: "..tostring(last))
assert(a == 2 and b == 1,
       "izid ni 2-1 (selfkill mora dati točko nasprotniku): "..tostring(last))
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
assert(et_ClientCommand(0, "arenahp") == 1, "svoj ukaz mora prevzeti")
health[0] = 245
et_Damage(1, 0, 40, 0, 8)
assert(health[0] == 250, "⛔ strop mora ostati posnet na 250: "..health[0])
argv = {"arenahp", "250"}
et_ClientCommand(0, "arenahp")
-- ⛔ Ukazna pot mora prilepiti prav tako kot bralna. Prvi zapis tega primera je
--    uporabljal 250, ki JE preset — mutacija »ne prilepi« je zato prešla, ker
--    se vhod in izhod nista razlikovala. Vzemi vrednost, ki se MORA premakniti.
argv = {"arenahp", "700"}
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
