-- endstats.lua modified by x0rnn, shows some interesting game statistics at the end of a round
-- Modified to save EndStats awards to gamestats files for Discord bot integration
-- Creates files with _endstats.txt suffix to not interfere with existing c0rnp0rn3 stats

killing_sprees = {}
death_sprees = {}
kmulti         = {}
kendofmap      = false
eomap_done = false
eomaptime = 0
gamestate   = -1
topshots = {}
mkps = {}
denies = {}
intermission = false
weaponstats = {}
endplayers = {}
endplayerscnt = 0
tblcount = 0
vsstats = {}
vsstats_kills = {}
vsstats_deaths = {}
kills = {}
deaths = {}
worst_enemy = {}
easiest_prey = {}
vsstats = {}
vsstats_kills = {}
vsstats_deaths = {}
hitters = {}
light_weapons = {1,2,3,5,6,7,8,9,10,11,12,13,14,17,37,38,44,45,46,50,51,53,54,55,56,61,62,66}
explosives = {15,16,18,19,20,22,23,26,39,40,41,42,52,63,64}
HR_HEAD = 0
HR_ARMS = 1
HR_BODY = 2
HR_LEGS = 3
HR_NONE = -1
HR_TYPES = {HR_HEAD, HR_ARMS, HR_BODY, HR_LEGS}
hitRegionsData = {}
death_time = {}
death_time_total = {}
players = {}
ltm2 = 0
redspawn = 0
bluespawn = 0
redspawn2 = 0
bluespawn2 = 0
spawns = {}
redflag = false
blueflag = false
redlimbo1 = 0
bluelimbo1 = 0
redlimbo2 = 0
bluelimbo2 = 0
changedred = false
changedblue = false
paused = false

-- EndStats awards data structure
endstats_awards = {}

topshot_names = { 
    [1]="Most damage given", 
    [2]="Most damage received", 
    [3]="Most team damage given", 
    [4]="Most team damage received", 
    [5]="Most teamkills", 
    [6]="Most selfkills", 
    [7]="Most deaths", 
    [8]="Most kills per minute", 
    [9]="Quickest multikill w/ light weapons", 
    [11]="Farthest riflenade kill", 
    [12]="Most light weapon kills", 
    [13]="Most pistol kills", 
    [14]="Most rifle kills", 
    [15]="Most riflenade kills", 
    [16]="Most sniper kills", 
    [17]="Most knife kills", 
    [18]="Most air support kills", 
    [19]="Most mine kills", 
    [20]="Most grenade kills", 
    [21]="Most panzer kills", 
    [22]="Most mortar kills", 
    [23]="Most panzer deaths", 
    [24]="Mortarmagnet", 
    [25]="Most multikills", 
    [26]="Most MG42 kills", 
    [27]="Most MG42 deaths", 
    [28]="Most revives", 
    [29]="Most revived", 
    [30]="Best K/D ratio", 
    [31]="Most dynamites planted", 
    [32]="Most dynamites defused", 
    [33]="Most doublekills", 
    [34]="Longest killing spree", 
    [35]="Longest death spree", 
    [36]="Most objectives stolen", 
    [37]="Most objectives returned", 
    [38]="Most corpse gibs", 
    [39]="Most kill assists", 
    [40]="Most killsteals", 
    [41]="Most headshot kills", 
    [42]="Most damage per minute", 
    [43]="Tank/Meatshield (Refuses to die)", 
    [44]="Most useful kills (>Half respawn time left)", 
    [45]="Full respawn king", 
    [46]="Least time dead (What spawn?)", 
    [47]="Most playtime denied", 
    [48]="Most useless kills" 
}

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname("endstats.lua (modified for gamestats) "..et.FindSelf())
    sv_maxclients = tonumber(et.trap_Cvar_Get("sv_maxclients"))

    local i = 0
    for i=0, sv_maxclients-1 do
        killing_sprees[i] = 0
        death_sprees[i] = 0
        kmulti[i] = { [1]=0, [2]=0 }
        topshots[i] = { [1]=0, [2]=0, [3]=0, [4]=0, [5]=0, [6]=0, [7]=0, [8]=0, [9]=0, [10]=0, [11]=0, [12]=0, [13]=0, [14]=0, [15]=0, [16]=0, [17]=0, [18]=0, [19]=0, [20]=0, [21]=0, [22]=0, [23]=0, [24]=0, [25]=0, [26]=0, [27]=0, [28]=0, [29]=0, [30]=0, [31]=0, [32]=0, [33]=0, [34]=0, [35]=0, [36]=0 }
        mkps[i] = { [1]=0, [2]=0, [3]=0 }
        denies[i] = { [1]=false, [2]=-1, [3]=0 }
        vsstats[i]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
        vsstats_kills[i]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
        vsstats_deaths[i]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
        worst_enemy[i]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
        easiest_prey[i]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
        kills[i] = 0
        deaths[i] = 0
        hitters[i] = {nil, nil, nil, nil}
        death_time[i] = 0
        death_time_total[i] = 0
        spawns[i] = nil
    end
end

local function roundNum(num, n)
    local mult = 10^(n or 0)
    return math.floor(num * mult + 0.5) / mult
end

function getKeysSortedByValue(tbl, sortFunction)
    local keys = {}
    for key in pairs(tbl) do
        table.insert(keys, key)
    end

    table.sort(keys, function(a, b)
        return sortFunction(tbl[a], tbl[b])
    end)
    
    return keys
end

function has_value (tab, val)
    for index, value in ipairs(tab) do
        if value == val then
            return true
        end
    end
    return false
end

function getAllHitRegions(clientNum)
    local regions = {}
    for index, hitType in ipairs(HR_TYPES) do
        regions[hitType] = et.gentity_get(clientNum, "pers.playerStats.hitRegions", hitType)
    end       
    return regions
end     

function hitType(clientNum)
    local playerHitRegions = getAllHitRegions(clientNum)
    if hitRegionsData[clientNum] == nil then
        hitRegionsData[clientNum] = playerHitRegions
        return 2
    end
    for index, hitType in ipairs(HR_TYPES) do
        if playerHitRegions[hitType] > hitRegionsData[clientNum][hitType] then
            hitRegionsData[clientNum] = playerHitRegions
            return hitType
        end     
    end
    hitRegionsData[clientNum] = playerHitRegions
    return -1
end

-- Function to calculate and store EndStats awards based on original script logic
function calculateEndStatsAwards()
    local max = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 100, 0, 100, 0, 0}
    local max_id = {-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1}
    
    endstats_awards = {} -- Reset awards
    
    local i = 0
    for i=0, sv_maxclients-1 do
        if et.gentity_get(i, "pers.connected") == 2 then
            local team = tonumber(et.gentity_get(i, "sess.sessionTeam"))
            if team == 1 or team == 2 then
                local dg = tonumber(et.gentity_get(i, "sess.damage_given"))
                local dr = tonumber(et.gentity_get(i, "sess.damage_received"))
                local tdg = tonumber(et.gentity_get(i, "sess.team_damage"))
                local tdr = tonumber(et.gentity_get(i, "sess.team_received"))
                local tk = tonumber(et.gentity_get(i, "sess.team_kills"))
                local sk = tonumber(et.gentity_get(i, "sess.self_kills"))
                local d = tonumber(et.gentity_get(i, "sess.deaths"))
                local k = tonumber(et.gentity_get(i, "sess.kills"))
                local gibs = tonumber(et.gentity_get(i, "sess.gibs"))
                local kd = 0
                
                if d ~= 0 then
                    kd = k/d
                else
                    kd = k + 1
                end
                
                -- Calculate awards using same logic as original topshots_f function
                -- damage given
                if dg > max[1] then max[1] = dg; max_id[1] = i end
                -- damage received
                if dr > max[2] then max[2] = dr; max_id[2] = i end
                -- team damage given
                if tdg > max[3] then max[3] = tdg; max_id[3] = i end
                -- team damage received
                if tdr > max[4] then max[4] = tdr; max_id[4] = i end
                -- teamkills
                if tk > max[5] then max[5] = tk; max_id[5] = i end
                -- selfkills
                if sk > max[6] then max[6] = sk; max_id[6] = i end
                -- deaths
                if d > max[7] then max[7] = d; max_id[7] = i end
                -- most revives (from topshots[i][20])
                if topshots[i] and topshots[i][20] and topshots[i][20] > max[28] then max[28] = topshots[i][20]; max_id[28] = i end
                -- most revived (from topshots[i][21])
                if topshots[i] and topshots[i][21] and topshots[i][21] > max[29] then max[29] = topshots[i][21]; max_id[29] = i end
                -- k/d ratio
                if k > 9 and kd > max[30] then max[30] = kd; max_id[30] = i end
                -- most dynamites planted (from topshots[i][22])
                if topshots[i] and topshots[i][22] and topshots[i][22] > max[31] then max[31] = topshots[i][22]; max_id[31] = i end
                -- most dynamites defused (from topshots[i][23])
                if topshots[i] and topshots[i][23] and topshots[i][23] > max[32] then max[32] = topshots[i][23]; max_id[32] = i end
                -- longest kill spree (from topshots[i][25])
                if topshots[i] and topshots[i][25] and topshots[i][25] > max[34] then max[34] = topshots[i][25]; max_id[34] = i end
                -- longest death spree (from topshots[i][26])
                if topshots[i] and topshots[i][26] and topshots[i][26] > max[35] then max[35] = topshots[i][26]; max_id[35] = i end
                -- most objectives stolen (from topshots[i][27])
                if topshots[i] and topshots[i][27] and topshots[i][27] > max[36] then max[36] = topshots[i][27]; max_id[36] = i end
                -- most objectives returned (from topshots[i][28])
                if topshots[i] and topshots[i][28] and topshots[i][28] > max[37] then max[37] = topshots[i][28]; max_id[37] = i end
                -- most gibs
                if gibs > max[38] then max[38] = gibs; max_id[38] = i end
                -- most kill assists (from topshots[i][29])
                if topshots[i] and topshots[i][29] and topshots[i][29] > max[39] then max[39] = topshots[i][29]; max_id[39] = i end
                -- most killsteals (from topshots[i][30])
                if topshots[i] and topshots[i][30] and topshots[i][30] > max[40] then max[40] = topshots[i][30]; max_id[40] = i end
                -- most headshot kills (from topshots[i][31])
                if topshots[i] and topshots[i][31] and topshots[i][31] > max[41] then max[41] = topshots[i][31]; max_id[41] = i end
            end
        end
    end
    
    -- Create award entries for winners
    local award_mapping = {
        [1] = "Most damage given",
        [2] = "Most damage received", 
        [3] = "Most team damage given",
        [4] = "Most team damage received",
        [5] = "Most teamkills",
        [6] = "Most selfkills",
        [7] = "Most deaths",
        [28] = "Most revives",
        [29] = "Most revived",
        [30] = "Best K/D ratio",
        [31] = "Most dynamites planted",
        [32] = "Most dynamites defused",
        [34] = "Longest killing spree",
        [35] = "Longest death spree", 
        [36] = "Most objectives stolen",
        [37] = "Most objectives returned",
        [38] = "Most corpse gibs",
        [39] = "Most kill assists",
        [40] = "Most killsteals",
        [41] = "Most headshot kills"
    }
    
    for award_id, award_name in pairs(award_mapping) do
        if max_id[award_id] ~= -1 and max[award_id] > 0 then
            local winner_name = et.gentity_get(max_id[award_id], "pers.netname")
            local userinfo = et.trap_GetUserinfo(max_id[award_id])
            local winner_guid = string.upper(et.Info_ValueForKey(userinfo, "cl_guid"))
            
            endstats_awards[award_id] = {
                name = award_name,
                winner = winner_name,
                guid = winner_guid,
                value = max[award_id]
            }
        end
    end
end

-- Original topshots_f function from endstats.lua for 1:1 console output
function topshots_f(id)
	local max = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 100, 0, 100, 0, 0}
	local max_id = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}
	local i = 0
	for i=0, sv_maxclients-1 do
		if et.gentity_get(i, "pers.connected") == 2 then
			local team = tonumber(et.gentity_get(i, "sess.sessionTeam"))
			local damage_given = et.gentity_get(i, "sess.damage_given")
			local damage_received = et.gentity_get(i, "sess.damage_received")
			local team_damage_given = et.gentity_get(i, "sess.team_damage_given")
			local team_damage_received = et.gentity_get(i, "sess.team_damage_received")
			local gibs = et.gentity_get(i, "sess.gibs")
			local selfkills = et.gentity_get(i, "sess.self_kills")
			local teamkills = et.gentity_get(i, "sess.team_kills")
			local revives = et.gentity_get(i, "sess.revives")
			local ammogiven = et.gentity_get(i, "sess.ammogiven")
			local healthgiven = et.gentity_get(i, "sess.healthgiven")
			local obj_stolen = et.gentity_get(i, "sess.obj_stolen")
			local obj_returned = et.gentity_get(i, "sess.obj_returned")
			local kills = et.gentity_get(i, "sess.kills")
			local deaths = et.gentity_get(i, "sess.deaths")
			local dyn_planted = et.gentity_get(i, "sess.dyn_planted")
			local dyn_defused = et.gentity_get(i, "sess.dyn_defused")
			
			-- Calculate topshots values
			topshots[i][1] = damage_given
			topshots[i][2] = damage_received
			topshots[i][3] = team_damage_given
			topshots[i][4] = team_damage_received
			topshots[i][5] = teamkills
			topshots[i][6] = selfkills
			topshots[i][7] = deaths
			topshots[i][8] = topshots[i][8] or 0 -- kills per minute
			topshots[i][28] = revives
			topshots[i][29] = ammogiven + healthgiven
			topshots[i][30] = deaths > 0 and (kills / deaths) or kills
			topshots[i][31] = dyn_planted
			topshots[i][32] = dyn_defused
			topshots[i][34] = killing_sprees[i] or 0
			topshots[i][35] = death_sprees[i] or 0
			topshots[i][36] = obj_stolen
			topshots[i][37] = obj_returned
			topshots[i][38] = gibs
			topshots[i][39] = topshots[i][39] or 0
			topshots[i][40] = topshots[i][40] or 0
			topshots[i][41] = topshots[i][41] or 0
			topshots[i][42] = topshots[i][42] or 0
			
			-- Find maximums
			if damage_given > max[1] then max[1] = damage_given; max_id[1] = i end
			if damage_received > max[2] then max[2] = damage_received; max_id[2] = i end
			if team_damage_given > max[3] then max[3] = team_damage_given; max_id[3] = i end
			if team_damage_received > max[4] then max[4] = team_damage_received; max_id[4] = i end
			if teamkills > max[5] then max[5] = teamkills; max_id[5] = i end
			if selfkills > max[6] then max[6] = selfkills; max_id[6] = i end
			if deaths > max[7] then max[7] = deaths; max_id[7] = i end
			if topshots[i][28] > max[28] then max[28] = topshots[i][28]; max_id[28] = i end
			if topshots[i][29] > max[29] then max[29] = topshots[i][29]; max_id[29] = i end
			if topshots[i][30] > max[30] and deaths > 0 then max[30] = topshots[i][30]; max_id[30] = i end
			if topshots[i][31] > max[31] then max[31] = topshots[i][31]; max_id[31] = i end
			if topshots[i][32] > max[32] then max[32] = topshots[i][32]; max_id[32] = i end
			if topshots[i][34] > max[34] then max[34] = topshots[i][34]; max_id[34] = i end
			if topshots[i][35] > max[35] then max[35] = topshots[i][35]; max_id[35] = i end
			if topshots[i][36] > max[36] then max[36] = topshots[i][36]; max_id[36] = i end
			if topshots[i][37] > max[37] then max[37] = topshots[i][37]; max_id[37] = i end
			if topshots[i][38] > max[38] then max[38] = topshots[i][38]; max_id[38] = i end
			if topshots[i][39] > max[39] then max[39] = topshots[i][39]; max_id[39] = i end
			if topshots[i][40] > max[40] then max[40] = topshots[i][40]; max_id[40] = i end
			if topshots[i][41] > max[41] then max[41] = topshots[i][41]; max_id[41] = i end
			if topshots[i][42] > max[42] then max[42] = topshots[i][42]; max_id[42] = i end
		end
	end
	
	if id == -2 then
		-- Display the original endstats output exactly as it was
		et.trap_SendServerCommand(-1, "print \"\\n\"")
		
		if max[1] > 0 then
			local name = et.gentity_get(max_id[1], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[1] .. ": ^7" .. name .. " ^2(" .. max[1] .. ")\\n\"")
		end
		if max[2] > 0 then
			local name = et.gentity_get(max_id[2], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[2] .. ": ^7" .. name .. " ^2(" .. max[2] .. ")\\n\"")
		end
		if max[3] > 0 then
			local name = et.gentity_get(max_id[3], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[3] .. ": ^7" .. name .. " ^2(" .. max[3] .. ")\\n\"")
		end
		if max[5] > 0 then
			local name = et.gentity_get(max_id[5], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[5] .. ": ^7" .. name .. " ^2(" .. max[5] .. ")\\n\"")
		end
		if max[6] > 0 then
			local name = et.gentity_get(max_id[6], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[6] .. ": ^7" .. name .. " ^2(" .. max[6] .. ")\\n\"")
		end
		if max[7] > 0 then
			local name = et.gentity_get(max_id[7], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[7] .. ": ^7" .. name .. " ^2(" .. max[7] .. ")\\n\"")
		end
		if max[28] > 0 then
			local name = et.gentity_get(max_id[28], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[28] .. ": ^7" .. name .. " ^2(" .. max[28] .. ")\\n\"")
		end
		if max[29] > 0 then
			local name = et.gentity_get(max_id[29], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[29] .. ": ^7" .. name .. " ^2(" .. max[29] .. ")\\n\"")
		end
		if max[30] > 0 then
			local name = et.gentity_get(max_id[30], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[30] .. ": ^7" .. name .. " ^2(" .. roundNum(max[30], 2) .. ")\\n\"")
		end
		if max[31] > 0 then
			local name = et.gentity_get(max_id[31], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[31] .. ": ^7" .. name .. " ^2(" .. max[31] .. ")\\n\"")
		end
		if max[32] > 0 then
			local name = et.gentity_get(max_id[32], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[32] .. ": ^7" .. name .. " ^2(" .. max[32] .. ")\\n\"")
		end
		if max[34] > 0 then
			local name = et.gentity_get(max_id[34], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[34] .. ": ^7" .. name .. " ^2(" .. max[34] .. ")\\n\"")
		end
		if max[35] > 0 then
			local name = et.gentity_get(max_id[35], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[35] .. ": ^7" .. name .. " ^2(" .. max[35] .. ")\\n\"")
		end
		if max[36] > 0 then
			local name = et.gentity_get(max_id[36], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[36] .. ": ^7" .. name .. " ^2(" .. max[36] .. ")\\n\"")
		end
		if max[37] > 0 then
			local name = et.gentity_get(max_id[37], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[37] .. ": ^7" .. name .. " ^2(" .. max[37] .. ")\\n\"")
		end
		if max[38] > 0 then
			local name = et.gentity_get(max_id[38], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[38] .. ": ^7" .. name .. " ^2(" .. max[38] .. ")\\n\"")
		end
		if max[39] > 0 then
			local name = et.gentity_get(max_id[39], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[39] .. ": ^7" .. name .. " ^2(" .. max[39] .. ")\\n\"")
		end
		if max[40] > 0 then
			local name = et.gentity_get(max_id[40], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[40] .. ": ^7" .. name .. " ^2(" .. max[40] .. ")\\n\"")
		end
		if max[41] > 0 then
			local name = et.gentity_get(max_id[41], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[41] .. ": ^7" .. name .. " ^2(" .. max[41] .. ")\\n\"")
		end
		if max[42] > 0 then
			local name = et.gentity_get(max_id[42], "pers.netname")
			et.trap_SendServerCommand(-1, "print \"^2" .. topshot_names[42] .. ": ^7" .. name .. " ^2(" .. roundNum(max[42], 1) .. ")\\n\"")
		end
		
		et.trap_SendServerCommand(-1, "print \"\\n\"")
	end
end

-- Function to save EndStats awards to gamestats file (similar to c0rnp0rn3.lua format)
function SaveEndStatsAwards()
    local mapname = et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_SERVERINFO), "mapname")
    local round = tonumber(et.trap_Cvar_Get("g_currentRound")) == 0 and 2 or 1
    local fileName = string.format("gamestats\\%s%s-round-%d_endstats.txt", os.date('%Y-%m-%d-%H%M%S-'), mapname, round)
    local fileHandle = et.trap_FS_FOpenFile(fileName, et.FS_WRITE)

    -- Header data (similar to c0rnp0rn3.lua format)
    local servername = et.trap_Cvar_Get("sv_hostname")
    local config = et.trap_Cvar_Get("g_customConfig")
    local defenderteam = tonumber(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_INFO), "d") or "0") + 1
    local winnerteam = tonumber(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_MAPWINNER), "w") or "0") + 1
    local timelimit = tonumber(et.trap_Cvar_Get("timelimit") or "0")
    local nextTimeLimit = tonumber(et.trap_Cvar_Get("g_nextTimeLimit") or "0")
    local header = string.format("%s\\%s\\%s\\%d\\%d\\%d\\%0.2f\\%0.2f\n", servername, mapname, config or "", round, defenderteam, winnerteam, timelimit, nextTimeLimit)

    et.trap_FS_Write(header, string.len(header), fileHandle)

    -- Write EndStats awards data
    for award_id, award in pairs(endstats_awards) do
        if award and award.winner and award.name then
            local award_line = string.format("AWARD\\%d\\%s\\%s\\%s\\%s\n", 
                award_id, 
                award.name, 
                award.winner, 
                award.guid or "unknown", 
                tostring(award.value))
            et.trap_FS_Write(award_line, string.len(award_line), fileHandle)
        end
    end

    et.trap_FS_FCloseFile(fileHandle)
    et.G_LogPrint("EndStats: Saved awards to " .. fileName .. "\n")
end

-- Keep all the original endstats functions but add our new save functionality
function et_Damage(target, attacker, damage, damageFlags, meansOfDeath)
    if gamestate == 0 then
        if target ~= attacker and attacker ~= 1022 and attacker ~= 1023 and not (tonumber(target) < 0) and not (tonumber(target) > tonumber(et.trap_Cvar_Get("sv_maxclients"))) then
            if hitters[target] == nil then
                hitters[target] = {nil, nil, nil, nil}
            end
            hitters[target][1] = attacker
            hitters[target][2] = meansOfDeath
            hitters[target][3] = et.trap_Milliseconds()
            hitters[target][4] = hitType(target)
        end
    end
end

function checkMultiKill (id, mod)
    local lvltime = et.trap_Milliseconds()
    
    -- Initialize kmulti and mkps for new players
    if not kmulti[id] then
        kmulti[id] = {0, 0}
    end
    if not mkps[id] then
        mkps[id] = {0, 0, 0}
    end
    
    if (lvltime - kmulti[id][1]) < 3000 then
        kmulti[id][2] = kmulti[id][2] + 1
        if kmulti[id][2] == 2 then
            topshots[id][33] = topshots[id][33] + 1
        end
        if kmulti[id][2] >= 2 then
            topshots[id][25] = topshots[id][25] + 1
            if has_value(light_weapons, mod) then
                if mkps[id][3] == 0 or ((lvltime - mkps[id][1]) < (mkps[id][2] - mkps[id][1])) then
                    mkps[id][1] = mkps[id][1]
                    mkps[id][2] = lvltime
                    mkps[id][3] = 1
                end
            end
        end
    else
        kmulti[id][2] = 1
        mkps[id][1] = lvltime
        mkps[id][3] = 0
    end
    kmulti[id][1] = lvltime
end

function et_Obituary(victim, killer, mod)
    if gamestate == 0 then
        if killer ~= 1022 and killer ~= 1023 and not (tonumber(killer) < 0) and not (tonumber(killer) > tonumber(et.trap_Cvar_Get("sv_maxclients"))) then
            
            -- Initialize arrays for players if not already done (for mid-game joiners)
            if not killing_sprees[victim] then killing_sprees[victim] = 0 end
            if not death_sprees[victim] then death_sprees[victim] = 0 end
            if not killing_sprees[killer] then killing_sprees[killer] = 0 end
            if not death_sprees[killer] then death_sprees[killer] = 0 end
            
            if not topshots[killer] then
                topshots[killer] = { [1]=0, [2]=0, [3]=0, [4]=0, [5]=0, [6]=0, [7]=0, [8]=0, [9]=0, [10]=0, [11]=0, [12]=0, [13]=0, [14]=0, [15]=0, [16]=0, [17]=0, [18]=0, [19]=0, [20]=0, [21]=0, [22]=0, [23]=0, [24]=0, [25]=0, [26]=0, [27]=0, [28]=0, [29]=0, [30]=0, [31]=0, [32]=0, [33]=0, [34]=0, [35]=0, [36]=0 }
            end
            if not topshots[victim] then
                topshots[victim] = { [1]=0, [2]=0, [3]=0, [4]=0, [5]=0, [6]=0, [7]=0, [8]=0, [9]=0, [10]=0, [11]=0, [12]=0, [13]=0, [14]=0, [15]=0, [16]=0, [17]=0, [18]=0, [19]=0, [20]=0, [21]=0, [22]=0, [23]=0, [24]=0, [25]=0, [26]=0, [27]=0, [28]=0, [29]=0, [30]=0, [31]=0, [32]=0, [33]=0, [34]=0, [35]=0, [36]=0 }
            end
            
            if victim == killer then
                topshots[killer][6] = topshots[killer][6] + 1
            else
                killing_sprees[victim] = 0
                death_sprees[victim] = death_sprees[victim] + 1
                killing_sprees[killer] = killing_sprees[killer] + 1
                death_sprees[killer] = 0
                
                checkMultiKill(killer, mod)
                
                if topshots[killer][34] < killing_sprees[killer] then
                    topshots[killer][34] = killing_sprees[killer]
                end
                if topshots[victim][35] < death_sprees[victim] then
                    topshots[victim][35] = death_sprees[victim]
                end
                
                -- Track vs stats
                if vsstats[killer] and vsstats[victim] then
                    vsstats[killer][victim] = vsstats[killer][victim] + 1
                    vsstats_kills[killer][victim] = vsstats_kills[killer][victim] + 1
                end
                
                -- Track weapon kills for awards
                if has_value(light_weapons, mod) then
                    topshots[killer][12] = topshots[killer][12] + 1
                end
                
                -- Headshot tracking
                if hitters[victim] and hitters[victim][4] == HR_HEAD then
                    topshots[killer][41] = topshots[killer][41] + 1
                end
                
                -- Weapon-specific tracking
                if mod == 1 or mod == 2 then -- pistols
                    topshots[killer][13] = topshots[killer][13] + 1
                elseif mod == 3 or mod == 4 or mod == 5 then -- rifles  
                    topshots[killer][14] = topshots[killer][14] + 1
                elseif mod == 6 then -- knife
                    topshots[killer][17] = topshots[killer][17] + 1
                elseif mod == 11 then -- grenades
                    topshots[killer][20] = topshots[killer][20] + 1
                elseif mod == 8 or mod == 9 then -- panzer/bazooka
                    topshots[killer][21] = topshots[killer][21] + 1
                    topshots[victim][23] = topshots[victim][23] + 1
                elseif mod == 20 or mod == 21 then -- MG42/Browning
                    topshots[killer][26] = topshots[killer][26] + 1
                    topshots[victim][27] = topshots[victim][27] + 1
                elseif mod == 12 or mod == 13 then -- mortar
                    topshots[killer][22] = topshots[killer][22] + 1
                    topshots[victim][24] = topshots[victim][24] + 1
                end
            end
        end
    end
end

function et_Print(text)
    if gamestate == 0 then
        -- Handle various game events for stats tracking
        if string.find(text, "^Planted at") then
            local id = tonumber(string.sub(text, string.find(text, "Planted at") + 11, string.find(text, "Planted at") + 12))
            if id then
                topshots[id][31] = topshots[id][31] + 1
            end
        end
    end

    if kendofmap and string.find(text, "^WeaponStats: ") == 1 then
        local id = tonumber(string.sub(text, 15, 16))
        if id then
            local wstats = string.sub(text, 18)
            weaponstats[id] = wstats
        end
        return(nil)
    end

    if text == "Exit: Timelimit hit.\n" or text == "Exit: Wolf EndRound.\n" or text == "Exit: Allies Surrender\n" or text == "Exit: Axis Surrender\n" then
        kendofmap = true
        eomap_done = false
        eomaptime = et.trap_Milliseconds()
        
        -- Display EndStats to players when round ends (immediate feedback using original function)
        calculateEndStatsAwards()
        topshots_f(-2)
        
        return(nil)
    end
end

function et_RunFrame(levelTime)
    gamestate = tonumber(et.trap_Cvar_Get("gamestate"))

    if gamestate == et.GS_INTERMISSION and not intermission then
        -- Calculate EndStats awards when entering intermission
        calculateEndStatsAwards()
        
        -- Display awards to players in console/chat (original topshots_f behavior)
        topshots_f(-2)
        
        -- Save awards to gamestats file for Discord bot
        SaveEndStatsAwards()
        
        intermission = true
    end

    if gamestate ~= et.GS_INTERMISSION then
        intermission = false
    end

    if math.fmod(levelTime, 100) ~= 0 then return end
    local cs = tonumber(et.trap_GetConfigstring(et.CS_SERVERTOGGLES))
    if paused == false then
        if (cs & 8) == 8 then
            paused = true
        end
    elseif paused == true then
        if (cs & 8) ~= 8 then
            paused = false
        end
    end

    if math.fmod(levelTime, 500) ~= 0 then return end

    local ltm = et.trap_Milliseconds()
    if eomap_done then
        if ltm > (eomaptime + 3000) then
            -- Calculate and display one more time for safety
            calculateEndStatsAwards()
            topshots_f(-2)
        end
    end

    if math.fmod(levelTime, 1000) ~= 0 then return end
    if gamestate == 0 then
        for i = 0, sv_maxclients-1 do
            if et.gentity_get(i, "pers.connected") == 2 then
                local team = tonumber(et.gentity_get(i, "sess.sessionTeam"))
                if team == 1 or team == 2 then
                    death_time_total[i] = death_time_total[i] + death_time[i]
                    if death_time[i] > 0 then
                        death_time[i] = death_time[i] + 1
                    end
                end
            end
        end
    end
end

function et_ClientBegin(id)
    local team = tonumber(et.gentity_get(id, "sess.sessionTeam"))
    if players[id] == nil then
        players[id] = team
    end
end

function et_ClientUserinfoChanged(clientNum)
    local team = tonumber(et.gentity_get(clientNum, "sess.sessionTeam"))
    if players[clientNum] == nil then
        players[clientNum] = team
    end
    if players[clientNum] ~= team then
        -- Handle team changes
    end
    players[clientNum] = team
end

function et_ClientSpawn(id, revived)
    killing_sprees[id] = 0
    local team = tonumber(et.gentity_get(id, "sess.sessionTeam"))
    if revived ~= 1 then
        death_sprees[id] = 0
        local team = tonumber(et.gentity_get(id, "sess.sessionTeam"))
    end
    hitters[id] = {nil, nil, nil, nil}
    hitRegionsData[id] = getAllHitRegions(id)
    if team == 1 or team == 2 then
        if spawns[id] == nil then
            spawns[id] = et.trap_Milliseconds()
        end
    end
    death_time[id] = 0
end

function et_ClientDisconnect(id)
    killing_sprees[id] = 0
    death_sprees[id] = 0
    topshots[id] = { [1]=0, [2]=0, [3]=0, [4]=0, [5]=0, [6]=0, [7]=0, [8]=0, [9]=0, [10]=0, [11]=0, [12]=0, [13]=0, [14]=0, [15]=0, [16]=0, [17]=0, [18]=0, [19]=0, [20]=0, [21]=0, [22]=0, [23]=0, [24]=0, [25]=0, [26]=0, [27]=0, [28]=0, [29]=0, [30]=0, [31]=0, [32]=0, [33]=0, [34]=0, [35]=0, [36]=0 }
    mkps[id] = { [1]=0, [2]=0, [3]=0 }
    vsstats[id]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
    vsstats_kills[id]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
    vsstats_deaths[id]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
    worst_enemy[id]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
    easiest_prey[id]={[0]=0,[1]=0,[2]=0,[3]=0,[4]=0,[5]=0,[6]=0,[7]=0,[8]=0,[9]=0,[10]=0,[11]=0,[12]=0,[13]=0,[14]=0,[15]=0,[16]=0,[17]=0,[18]=0,[19]=0,[20]=0,[21]=0,[22]=0,[23]=0,[24]=0,[25]=0,[26]=0,[27]=0,[28]=0,[29]=0,[30]=0,[31]=0,[32]=0,[33]=0,[34]=0,[35]=0,[36]=0,[37]=0,[38]=0,[39]=0,[40]=0,[41]=0,[42]=0,[43]=0,[44]=0,[45]=0,[46]=0,[47]=0,[48]=0,[49]=0,[50]=0,[51]=0,[52]=0,[53]=0,[54]=0,[55]=0,[56]=0,[57]=0,[58]=0,[59]=0,[60]=0,[61]=0,[62]=0,[63]=0}
    kills[id] = 0
    deaths[id] = 0
    hitters[id] = {nil, nil, nil, nil}
    death_time[id] = 0
    death_time_total[id] = 0
    spawns[id] = nil
end