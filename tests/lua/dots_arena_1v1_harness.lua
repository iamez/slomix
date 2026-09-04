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
local health = {[0]=100, [1]=100}
local team   = {[0]=1,   [1]=2}
local conn   = {[0]=2,   [1]=2}
local shield = {[0]=0,   [1]=0}
local cvars  = {sv_maxclients="2", arena_1v1="1", arena_1v1_map="dots_arena",
                arena_1v1_test="1", arena_1v1_log="1", g_forcerespawn="0"}
local argv   = {}
et = {
  TEAM_AXIS=1, TEAM_ALLIES=2, STAT_HEALTH=0, CS_SERVERINFO=0, PW_INVULNERABLE=1,
  MOD_SUICIDE=37, FS_APPEND=2,
  RegisterModname=function() end, G_Print=function() end,
  trap_Cvar_Get=function(n) return cvars[n] or "" end,
  trap_Cvar_Set=function(n,v) cvars[n]=v; calls[#calls+1]="cvar "..n.."="..v end,
  trap_GetConfigstring=function() return "\\mapname\\dots_arena" end,
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
  trap_SendServerCommand=function(cn, cmd) sent[#sent+1]=cmd end,
  gentity_set=function(cn, field, idx, val)
    if field=="ps.powerups" and idx==1 then shield[cn]=val end
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
et.trap_GetConfigstring = function() return "\\mapname\\supply" end
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
et.trap_GetConfigstring = function() return "\\mapname\\dots_arena" end
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
et.trap_GetConfigstring = function() return "\\mapname\\dots_arena" end
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
