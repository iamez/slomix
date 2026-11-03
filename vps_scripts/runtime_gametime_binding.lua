-- Trusted same-VM host-ticket bridge. Does not load/install callbacks or scripts.
local completion=require('runtime_host_timing_completion')
local identity=require('runtime_round_identity')
local M={}

function M.prepare(options,bind,now)
    assert(type(options)=='table' and type(bind)=='function' and type(now)=='function',
        'explicit trusted timing provisioning required')
    local allowed={source_id=true,producer_spool=true,timing_sockets=true,timeout_ms=true}
    for key in pairs(options) do assert(allowed[key],'unknown timing provisioning option') end
    local source,spool,timeout=options.source_id,options.producer_spool,options.timeout_ms
    assert(type(source)=='string' and #source<=64 and source:match('^[a-z0-9][a-z0-9_.%-]*$'),
        'invalid trusted source')
    assert(type(spool)=='string' and spool:sub(1,1)=='/' and not spool:find('%z')
        and not spool:find('..',1,true),'explicit producer spool required')
    assert(type(timeout)=='number' and timeout>0 and timeout<=10000,'bounded timing timeout required')
    assert(type(options.timing_sockets)=='table','independent timing sockets required')
    local paths={}
    for half,path in pairs(options.timing_sockets) do
        assert((half==1 or half==2) and type(path)=='string' and path:sub(1,1)=='/'
            and #path<=107 and not path:find('%z'),'invalid timing socket')
        paths[half]=path
    end
    assert(paths[1] and paths[2] and paths[1]~=paths[2],'two distinct timing sockets required')
    require('socket.unix') -- Preload dependencies outside all game callbacks.
    return function(ticket)
        assert(type(ticket)=='table','accepted host ticket required')
        local wire=identity.encode(ticket.identity)
        local half=ticket.identity.round_number
        assert(ticket.identity.source_id==source,'timing ticket source mismatch')
        local generation=ticket.generation
        assert(type(generation)=='string' and #generation==32 and generation:match('^[0-9a-f]+$'),
            'invalid timing generation')
        local sender=completion.sender(paths[half],now,timeout)
        assert(bind(ticket.identity,ticket.map_name,{generation=generation,
            directory=spool..'/'..generation,completed=sender.completed})==wire,
            'timing binding not confirmed')
    end
end
return M
