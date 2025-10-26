--[[
    ET: Legacy
    Copyright (C) 2012-2022 ET:Legacy team <mail@etlegacy.com>

    This file is part of ET: Legacy - http://www.etlegacy.com

    ET: Legacy is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    ET: Legacy is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with ET: Legacy. If not, see <http://www.gnu.org/licenses/>.
]]--

local modname = "game-stats"
local version = "0.2"

-- local constants

local storeTimeInterval = 10000 -- how often we store players stats
local CON_CONNECTED     = 2
local WS_KNIFE          = 0
local WS_MAX            = 28
local STAT_XP           = 5

-- local variables

local maxClients     = 20
local nextStoreTime  = 0
local intermission   = false
local stats          = {}

-- char *G_createStats(gentity_t *ent) g_match.c
function StoreStats()
	for i = 0, max_clients - 1 do
	    if et.gentity_get(i, "pers.connected") == CON_CONNECTED then
			local dwWeaponMask = 0
			local aWeaponStats = {}
			local weaponStats  = ""

			for j = WS_KNIFE, WS_MAX - 1 do
				 aWeaponStats[j] = et.gentity_get(i, "sess.aWeaponStats", j)

				 local atts      = aWeaponStats[j][1]
				 local deaths    = aWeaponStats[j][2]
				 local headshots = aWeaponStats[j][3]
				 local hits      = aWeaponStats[j][4]
				 local kills     = aWeaponStats[j][5]

				 if atts ~= 0 or hits ~= 0 or deaths ~= 0 or kills ~= 0 then
					 weaponStats  = string.format("%s %d %d %d %d %d", weaponStats, hits, atts, kills, deaths, headshots)
					 dwWeaponMask = dwWeaponMask | (1 << j)
				 end
			end

			if dwWeaponMask ~= 0 then
			    local userinfo     = et.trap_GetUserinfo(i) 
                local guid         = string.upper(et.Info_ValueForKey(userinfo, "cl_guid"))
			    local name         = et.gentity_get(i, "pers.netname")
			    local rounds       = et.gentity_get(i, "sess.rounds")
				local team         = et.gentity_get(i, "sess.sessionTeam")

				local damageGiven        = et.gentity_get(i, "sess.damage_given")
				local damageReceived     = et.gentity_get(i, "sess.damage_received")
				local teamDamageGiven    = et.gentity_get(i, "sess.team_damage_given")
				local teamDamageReceived = et.gentity_get(i, "sess.team_damage_received")
				local gibs               = et.gentity_get(i, "sess.gibs")
				local selfkills          = et.gentity_get(i, "sess.self_kills")
				local teamkills          = et.gentity_get(i, "sess.team_kills")
				local teamgibs           = et.gentity_get(i, "sess.team_gibs")
				local timeAxis           = et.gentity_get(i, "sess.time_axis")
				local timeAllies         = et.gentity_get(i, "sess.time_allies")
				local timePlayed         = et.gentity_get(i, "sess.time_played")
				local xp                 = et.gentity_get(i, "ps.stats", STAT_XP)
				timePlayed               = timeAxis + timeAllies == 0 and 0 or (100.0 * timePlayed / (timeAxis + timeAllies))
				
				stats[guid] = string.format("%s\\%s\\%d\\%d\\%d%s", string.sub(guid, 1, 8), name, rounds, team, dwWeaponMask, weaponStats)
				stats[guid] = string.format("%s %d %d %d %d %d %d %d %d %0.1f %d\n", stats[guid], damageGiven, damageReceived, teamDamageGiven, teamDamageReceived, gibs, selfkills, teamkills, teamgibs, timePlayed, xp)
			end
		end
	end
end

function SaveStats()
    local mapname      = et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_SERVERINFO), "mapname")
    local round        = tonumber(et.trap_Cvar_Get("g_currentRound")) == 0 and 2 or 1
    local fileName     = string.format("gamestats\\%s%s-round-%d.txt", os.date('%Y-%m-%d-%H%M%S-'), mapname, round)
	local fileHandle   = et.trap_FS_FOpenFile(fileName, et.FS_WRITE)

	-- header data
	local servername    = et.trap_Cvar_Get("sv_hostname")
	local config        = et.trap_Cvar_Get("g_customConfig")
	local defenderteam  = tonumber(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_INFO), "d")) + 1 -- change from scripting value for winner (0==AXIS, 1==ALLIES) to spawnflag value
	local winnerteam    = tonumber(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_MAPWINNER), "w")) + 1 -- change from scripting value for winner (0==AXIS, 1==ALLIES) to spawnflag value
	local timelimit     = tonumber(et.trap_Cvar_Get("timelimit"))
	local nextTimeLimit = tonumber(et.trap_Cvar_Get("g_nextTimeLimit"))
	local header        = string.format("%s\\%s\\%s\\%d\\%d\\%d\\%0.2f\\%0.2f\n", servername, mapname, config, round, defenderteam, winnerteam, timelimit, nextTimeLimit)

	et.trap_FS_Write(header, string.len(header), fileHandle);

	for i, value in pairs(stats) do
	    et.trap_FS_Write(value, string.len(value), fileHandle);
	end

	et.trap_FS_FCloseFile(fileHandle)
end

function et_RunFrame(levelTime)
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate"))

	-- store stats in case player leaves prematurely
	if levelTime >= nextStoreTime then
        StoreStats()
	    nextStoreTime = levelTime + storeTimeInterval
	end

	if gamestate == et.GS_INTERMISSION and not intermission then
	    StoreStats()
	    SaveStats()
	    intermission = true
	end

	if gamestate ~= et.GS_INTERMISSION then
	    intermission = false
	end
end

function et_InitGame()
    et.RegisterModname(modname .. " " .. version)

	max_clients = tonumber(et.trap_Cvar_Get("sv_maxClients"))
end
