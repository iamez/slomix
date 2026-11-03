-- Explicit same-VM callback composition. No loading, installation or activation.
local M = {}
local names = {'et_InitGame','et_RunFrame','et_ShutdownGame','et_Obituary',
    'et_ClientSpawn','et_ClientDisconnect','et_ClientUserinfoChanged','et_Damage',
    'et_Print','et_ClientCommand','et_IPCReceive'}
local allowed = {}
for _,name in ipairs(names) do allowed[name]=true end
local unpack_values = table.unpack or unpack
local function pack(...) return {n=select('#',...),...} end

function M.capture(environment)
    assert(type(environment)=='table','explicit callback environment required')
    for name,callback in pairs(environment) do
        if type(name)=='string' and name:match('^et_') and type(callback)=='function' then
            assert(allowed[name],'unsupported engine callback must not be silently dropped')
        end
    end
    local result={}
    for _,name in ipairs(names) do
        local callback=environment[name]
        assert(callback==nil or type(callback)=='function','invalid engine callback')
        result[name]=callback
    end
    return result
end

function M.compose(stats,timing)
    assert(type(stats)=='table' and type(timing)=='table','explicit callback tables required')
    for _,callbacks in ipairs({stats,timing}) do
        for name,callback in pairs(callbacks) do
            assert(allowed[name] and type(callback)=='function','unknown or invalid engine callback')
        end
    end
    local result={}
    for _,name in ipairs(names) do
        local event=name
        local first,second=stats[name],timing[name]
        assert(not first or first~=second,'inherited callback would execute twice')
        if first and second then
            result[name]=function(...)
                local a=pack(pcall(first,...))
                if a[1] and event=='et_ClientCommand' and a[2]==1 then return 1 end
                local b=pack(pcall(second,...))
                -- Both components observe lifecycle events even if one raises.
                -- Rethrow after preserving the other component's opportunity.
                if not a[1] then error(a[2],0) end
                if not b[1] then error(b[2],0) end
                if event=='et_ClientCommand' and b[2]==1 then return 1 end
                if a[2]~=nil then return unpack_values(a,2,a.n) end
                return unpack_values(b,2,b.n)
            end
        else
            result[name]=first or second
        end
    end
    return result
end
return M
