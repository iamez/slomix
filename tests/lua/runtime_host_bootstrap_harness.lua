-- Deterministic source state machine faults; native whole-c0rn proof separate.
local root, scenario, wire, context = arg[1], arg[2], arg[3], arg[4]
package.path=root .. "/vps_scripts/?.lua;" .. package.path
local module=require("runtime_host_bootstrap")
local decode=require("runtime_stats_delivery").decode
local value=decode(wire)
local reads, applied, closed, sends=0,0,false,{}
local channel={}
function channel.close() closed=true end
function channel.send_line(message)
    if scenario=="hello-error" or (scenario=="ack-error" and #sends>0) then error("fixture send error") end
    sends[#sends+1]=message
end
local pending=true
function channel.receive_line()
    reads=reads+1
    if scenario=="pending" and pending then pending=false; return nil end
    if #sends==1 and (reads==1 or scenario=="pending" and reads==2) then
        if scenario=="bad-context" then return "bad-context" end
        if scenario=="wrong-process" then return context:gsub(value.process_epoch,string.rep("f",32)) end
        if scenario=="wrong-life" then return context:gsub(value.lifecycle_epoch,string.rep("f",32)) end
        if scenario=="wrong-source" then
            local changed=context:match("^(.*)|[^|]+$") .. "|other-source"
            assert(changed ~= context, "source fault did not change context")
            return changed
        end
        return context
    end
    if scenario=="malformed" then return "malformed" end
    return wire
end
local expected_source=value.identity.source_id
local function capture()
    local observed="slomix_init_v1|1234|supply|1"
    if scenario=="time" then observed="slomix_init_v1|1235|supply|1" end
    if scenario=="map" then observed="slomix_init_v1|1234|radar|1" end
    if scenario=="half" then observed="slomix_init_v1|1234|supply|2" end
    return observed,function(proposed, completed)
        applied=applied+1
        assert(type(completed)=="function" and proposed.identity.round_id==value.identity.round_id)
        if scenario=="callback-error" then error("fixture binding failure") end
        if scenario=="bad-return" then return "other",proposed.generation end
        return proposed.identity.round_id,proposed.generation
    end
end
local function open()
    if scenario=="open-error" then error("fixture open error") end
    return channel
end
local client=module.start(capture,open,expected_source,function() end)
if scenario=="cancel" then
    client.close()
    assert(client.poll()=="cancelled" and applied==0 and #sends==1 and closed)
    return
end
local status
for _=1,5 do status=client.poll() end
assert(status==client.status())
local final_reads=reads
for _=1,5 do assert(client.poll()==status) end
assert(reads==final_reads and applied<=1, "terminal state retried IO/application")
if scenario=="ok" or scenario=="pending" then
    assert(status=="accepted" and applied==1 and #sends==2 and closed)
    assert(sends[2]=="slomix_stats_ack_v1" .. wire:sub(#"slomix_stats_bind_v1"+1), "non-exact ACK")
elseif scenario=="callback-error" or scenario=="bad-return" or scenario=="ack-error" then
    assert(status=="unconfirmed" and applied==1 and #sends==1 and closed, "ambiguous bind accepted/retried")
else
    assert(status=="failed" and applied==0 and #sends<=1, "invalid response reached binding")
    assert(closed or scenario=="open-error")
end
print("SOURCE BOOTSTRAP " .. scenario .. " state=" .. status .. " applied=" .. applied)
