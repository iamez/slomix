local root, fault, generation = arg[1], arg[2], arg[3]
package.path=root .. "/vps_scripts/?.lua;" .. package.path
local opens, sends, closes, output = 0, 0, 0, nil
package.loaded["socket.unix"] = {}
package.loaded.runtime_host_channel = {open=function(path, now, timeout)
    assert(path=="/trusted/completion" and now()==123 and timeout==250)
    opens=opens+1
    if fault=="open-error" then error("fixture open failed") end
    return {
        send_line=function(wire)
            sends=sends+1; output=wire
            if fault=="send-error" then error("fixture ambiguous send") end
        end,
        receive_line=function() error("completion waited for ACK") end,
        close=function() closes=closes+1 end,
    }
end}
local sender=require("runtime_host_completion").sender("/trusted/completion",function() return 123 end,250)
local receipt={version=1,state="writer_closed",filename="2026-09-25-120000-supply-round-1.txt",bytes=42}
if fault=="state" then receipt.state="round_ended"
elseif fault=="extra" then receipt.sha256="guessed"
elseif fault=="version" then receipt.version="1"
elseif fault=="size-zero" then receipt.bytes=0
elseif fault=="size-big" then receipt.bytes=8388609
elseif fault=="size-float" then receipt.bytes=1.5
elseif fault=="size-nan" then receipt.bytes=0/0
elseif fault=="size-string" then receipt.bytes="42"
elseif fault=="path" then receipt.filename="../" .. receipt.filename
elseif fault=="protocol" then receipt.filename=receipt.filename:gsub("%.txt$","_engagements.txt")
elseif fault=="generation" then generation="WRONG" end
assert(sender.status()=="ready")
local ok, error = pcall(sender.completed,receipt,generation)
assert(ok==(fault=="ok"), tostring(error))
if fault=="ok" then
    assert(sender.status()=="sent_unconfirmed" and opens==1 and sends==1 and closes==1)
    print(output)
elseif fault=="send-error" then
    assert(sender.status()=="unconfirmed" and opens==1 and sends==1 and closes==1)
elseif fault=="open-error" then
    assert(sender.status()=="failed" and opens==1 and sends==0 and closes==0)
else assert(sender.status()=="failed" and opens==0 and sends==0 and closes==0) end
local before=opens+sends+closes
assert(not pcall(sender.completed,receipt,generation), "completion callback retried")
assert(before==opens+sends+closes, "retry performed IO")
