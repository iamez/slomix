"""Isolated ABI probe: embedded Lua API ONLY, never vmMain/game/service startup.

Caller explicitly approves the qagame binary and staged bundle before invoking
this subprocess. No signal, network listener, game syscall, InitGame or RunFrame.
et.trap_Milliseconds below is a stub; this is NOT an actual round/capture proof.
"""

import ctypes
import os
import re
import sys
from pathlib import Path


def main():
    library, bundle = sys.argv[1:3]
    if sys.argv[3:]:
        raise ValueError('Unknown explicit probe mode')
    if any(re.fullmatch(r'/[A-Za-z0-9_./-]+', path) is None for path in (library, bundle)):
        raise ValueError('Probe requires explicit restricted absolute paths')
    # Match src/sys/sys_loadlib.h Sys_LoadLibrary: RTLD_NOW, not RTLD_GLOBAL.
    engine = ctypes.CDLL(library, mode=os.RTLD_NOW | os.RTLD_LOCAL)
    def assert_private_symbols():
        if hasattr(ctypes.CDLL(None), 'lua_gettop'):
            raise AssertionError('Embedded Lua leaked into process-global lookup')

    assert_private_symbols()
    engine.luaL_newstate.argtypes = []
    engine.luaL_newstate.restype = ctypes.c_void_p
    engine.luaL_openlibs.argtypes = [ctypes.c_void_p]
    engine.luaL_openlibs.restype = None
    engine.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    engine.luaL_loadstring.restype = ctypes.c_int
    engine.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_ssize_t, ctypes.c_void_p]
    engine.lua_pcallk.restype = ctypes.c_int
    engine.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    engine.lua_tolstring.restype = ctypes.c_void_p
    engine.lua_close.argtypes = [ctypes.c_void_p]
    engine.lua_close.restype = None
    state = engine.luaL_newstate()
    if not state:
        raise RuntimeError('Embedded Lua allocation failed')
    try:
        engine.luaL_openlibs(state)
        script = f'''
local game = "{bundle}/legacy"
package.path = game .. "/?.lua;" .. game .. "/lualibs/?.lua"
package.cpath = game .. "/lualibs/?.so"
assert(_VERSION == "Lua 5.4", "Unexpected embedded Lua version")
et = {{trap_Milliseconds=function() return 1 end}}
local adapter = dofile(game .. "/slomix_runtime_entry.lua")
assert(adapter.bootstrap_status() == "waiting_init")
assert(adapter.completion_status() == "ready")
assert(package.searchpath("socket.unix", package.cpath) == game .. "/lualibs/socket/unix.so")
local unix = require("socket.unix")
local connection = assert(unix.stream())
assert(connection:close())
assert(type(et_InitGame) == "function" and type(et_RunFrame) == "function")
assert(type(et_ShutdownGame) == "function")
print("QAGAME EMBEDDED LUA54: staged unix + c0rn wrapper loaded; waiting_init; NOT running game callbacks")
'''
        code = engine.luaL_loadstring(state, script.encode('ascii'))
        if code == 0:
            code = engine.lua_pcallk(state, 0, 0, 0, 0, None)
        if code:
            size = ctypes.c_size_t()
            message = engine.lua_tolstring(state, -1, ctypes.byref(size))
            if message:
                print(ctypes.string_at(message, min(size.value, 4096)).decode('utf-8', 'replace'), file=sys.stderr)
            return 1
        assert_private_symbols()
        native = ctypes.CDLL(bundle + '/legacy/lualibs/socket/unix.so', mode=os.RTLD_NOW | os.RTLD_LOCAL)
        if ctypes.cast(native.lua_gettop, ctypes.c_void_p).value != ctypes.cast(engine.lua_gettop, ctypes.c_void_p).value:
            raise AssertionError('Native carrier resolves a different Lua implementation')
        mappings = Path('/proc/self/maps').read_text()
        if re.search(r'/liblua5\.[0-9]+\.so', mappings):
            raise AssertionError('Unexpected second Lua implementation mapped')
        mapped_paths = {line.split()[-1] for line in mappings.splitlines()}
        staged_unix = bundle + '/legacy/lualibs/socket/liblua5.4-socket-unix.so.2'
        # A dedicated workspace links the explicitly approved qagame inode;
        # observe its canonical mapping, not the operator-facing symlink spelling.
        if not {str(Path(library).resolve(strict=True)), bundle + '/legacy/lualibs/socket/unix.so', staged_unix} <= mapped_paths:
            raise AssertionError('Actual native mappings differ from approved staged paths')
        if {path for path in mapped_paths if '/liblua5.4-socket-unix.so' in path} != {staged_unix}:
            raise AssertionError('Unexpected non-staged LuaSocket dependency mapped')
        print('LOCAL SCOPE: engine/native Lua symbol addresses agree; no global promotion or second liblua')
        print('MAPPED PATHS: approved engine + staged carrier + staged LuaSocket only')
        return 0
    finally:
        engine.lua_close(state)


if __name__ == '__main__':
    raise SystemExit(main())
