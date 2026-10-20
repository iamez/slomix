-- Real protocol module, ET IPC APIs simulated. No live engine/authentication.
local root, wire, scenario = (table.unpack or unpack)(arg)
package.path = root .. "/vps_scripts/?.lua;" .. package.path
local protocol = require("runtime_stats_delivery")
local decoded = protocol.decode(wire)
local authority = {peer_slot=1, peer_name="authority", peer_signature=string.rep("a",40),
    process_epoch=decoded.process_epoch, lifecycle_epoch=decoded.lifecycle_epoch,
    init_time=decoded.init_time, source_id=decoded.identity.source_id}
local consumer = {}
for k,v in pairs(authority) do consumer[k]=v end
consumer.peer_slot=2; consumer.peer_name="c0rn"; consumer.peer_signature=string.rep("b",40)
local receiver, sender
local binds, sends, acks, lookups = 0, 0, 0, 0
local signature = string.rep("a",40)
local rx_api = {
    FindMod=function(slot)
        assert(slot == 1, "unsafe lookup")
        lookups=lookups+1
        return "authority", signature
    end,
    IPCSend=function(slot, message)
        assert(slot == 1)
        acks=acks+1
        if scenario == "ack-error" then error("fixture ack error") end
        if scenario == "ack-drop" then return 1 end
        assert(sender.receive(2, message))
        return 1
    end,
}
receiver=protocol.receiver(rx_api, authority, function(ticket)
    binds=binds+1
    if scenario == "bind-error" then error("fixture bind changed state then raised") end
    assert(ticket.identity.round_id == decoded.identity.round_id)
    return ticket.identity.round_id, ticket.generation
end, function() end)
sender=protocol.sender({
    FindMod=function(slot) assert(slot==2); return "c0rn", string.rep("b",40) end,
    IPCSend=function(slot, message)
        assert(slot==2); sends=sends+1
        if scenario == "send-error" then error("fixture IPC delivery error") end
        receiver.receive(1, message)
        return 1 -- Engine success, even if receiver declined application payload.
    end,
}, consumer, wire)
assert(sender.status()=="pending")
assert(not sender.receive(2, wire:gsub("_bind_", "_ack_")), "unsolicited ack accepted")

if scenario == "wrong-peer" then
    for _,slot in ipairs({-1,64,999,0,2}) do assert(not receiver.receive(slot,wire)) end
    assert(not receiver.receive(nil,wire))
    assert(lookups==0 and binds==0)
elseif scenario == "reused-slot" then
    signature=string.rep("c",40)
    assert(not receiver.receive(1,wire) and binds==0)
elseif scenario == "stale" or scenario == "stale-lifecycle" or scenario == "wrong-init" or scenario == "wrong-source" then
    local stale=wire:gsub(decoded.process_epoch, string.rep("d",32),1)
    if scenario=="stale-lifecycle" then stale=wire:gsub(decoded.lifecycle_epoch,string.rep("d",32),1) end
    if scenario=="wrong-init" then stale=wire:gsub("|1234|","|1235|",1) end
    if scenario=="wrong-source" then
        local count
        stale,count=wire:gsub(decoded.identity.source_id:gsub("(%W)","%%%1"),"other-source",1)
        assert(count==1, "source mutation did not execute")
    end
    assert(not receiver.receive(1,stale) and binds==0)
elseif scenario == "malformed" then
    for _,bad in ipairs({"",wire.."|extra",string.rep("x",513),wire.."\n"}) do
        assert(not receiver.receive(1,bad))
    end
    assert(binds==0)
elseif scenario == "pins-frozen" then
    authority.process_epoch=string.rep("d",32)
    authority.peer_slot=63
    assert(sender.send() and binds==1)
    assert(not receiver.flush() and acks==0)
    assert(receiver.flush() and sender.status()=="accepted")
elseif scenario == "conflict" then
    assert(sender.send() and binds==1)
    local conflicting=wire:gsub(decoded.generation,string.rep("e",32),1)
    assert(not receiver.receive(1,conflicting) and binds==1)
elseif scenario == "bind-error" then
    for _=1,3 do assert(sender.send()) end
    assert(binds==1 and not receiver.flush() and acks==0 and sender.status()=="unconfirmed")
elseif scenario == "send-error" then
    for _=1,8 do assert(not sender.send()) end
    assert(sends==3 and binds==0 and sender.status()=="unconfirmed")
elseif scenario == "ack-drop" or scenario == "ack-error" then
    for _=1,8 do
        sender.send()
        receiver.flush()
        receiver.flush()
    end
    assert(sends==3 and acks==3 and binds==1 and sender.status()=="unconfirmed")
elseif scenario == "wrong-ack" then
    assert(sender.send())
    assert(not sender.receive(1,wire:gsub("_bind_","_ack_")))
    assert(not sender.receive(2,wire:gsub("_bind_","_ack_").."|extra"))
    assert(sender.status()=="pending")
else
    assert(scenario=="ok")
    assert(sender.send() and binds==1 and acks==0 and sender.status()=="pending")
    assert(sender.send() and binds==1, "duplicate caused rebind")
    assert(not receiver.flush() and acks==0, "ack sent on first receiver frame")
    assert(receiver.flush() and acks==1 and sender.status()=="accepted")
    assert(not sender.send() and sends==2)
    assert(receiver.receive(1,wire) and binds==1)
    assert(not receiver.flush() and receiver.flush() and acks==2)
end
print("IPC "..scenario.." binds="..binds.." sends="..sends.." acks="..acks)
