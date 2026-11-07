/* Test-only dependency stubs for extracted ET2.85 dispatch/stopwatch functions.
 * Not a game engine, Lua VM, filesystem, allocator or persistence rehearsal.
 */
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#define LUA_NUM_VM 2
#define GT_WOLF_STOPWATCH 3
#define CS_MULTI_INFO 1
#define CS_MULTI_MAPWINNER 2
typedef struct { int integer; double value; } cvar_t;
static cvar_t g_gametype = {3, 0}, g_currentRound, g_timelimit = {0, 20};
static struct { int timeCurrent, startTime; } level = {121000, 1000};
static int winner, defender, written_round, xp_calls;

static const char *va(const char *fmt, ...) {
    static char result[64]; va_list args; va_start(args, fmt);
    vsnprintf(result, sizeof result, fmt, args); va_end(args); return result;
}
static void trap_GetConfigstring(int key, char *out, unsigned long size) {
    snprintf(out, size, "%d", key);
}
static const char *Info_ValueForKey(const char *unused, const char *key) {
    (void)unused; return va("%d", !strcmp(key, "d") ? defender : winner);
}
static int Q_atoi(const char *value) { int n; assert(sscanf(value, "%d", &n) == 1); return n; }
static void trap_Cvar_Set(const char *key, const char *value) {
    if (!strcmp(key, "g_currentRound")) written_round = Q_atoi(value);
    /* Like the trap, do NOT immediately update the cached vmCvar integer. */
}
static void G_StoreMapXP(void) { xp_calls++; }

typedef struct { int target, last_integer, integers[3], count; const char *message; } lua_State;
typedef struct { int id, err; lua_State *L; } lua_vm_t;
static lua_State states[LUA_NUM_VM];
static lua_vm_t modules[LUA_NUM_VM];
static lua_vm_t *lVM[LUA_NUM_VM];
static int init_hooks, shutdown_hooks, frame_hooks, loads, unloads;
static int callback_present = 1, callback_ok = 1, deliveries, application_acks;
static int received_sender, received_nil_sender;
static const char *received_message;

static lua_vm_t *G_LuaGetVM(lua_State *L) {
    for (int i = 0; i < LUA_NUM_VM; i++) if (lVM[i] && lVM[i]->L == L) return lVM[i];
    return NULL;
}
static int luaL_checkinteger(lua_State *L, int arg) { assert(arg == 1); return L->target; }
static const char *luaL_checkstring(lua_State *L, int arg) { assert(arg == 2); return L->message; }
static void lua_pushinteger(lua_State *L, int value) {
    L->last_integer = value; if (L->count < 3) L->integers[L->count++] = value;
}
static void lua_pushnil(lua_State *L) { L->last_integer = -1; received_nil_sender++; }
static void lua_pushstring(lua_State *L, const char *value) { L->message = value; }
static int G_LuaGetNamedFunction(lua_vm_t *vm, const char *name) {
    vm->L->count = 0; (void)name; return callback_present;
}
static int G_LuaCall(lua_vm_t *vm, const char *name, int args, int results) {
    (void)results;
    if (!strcmp(name, "et_InitGame")) { assert(args == 3); init_hooks++; }
    if (!strcmp(name, "et_ShutdownGame")) { assert(args == 1); shutdown_hooks++; }
    if (!strcmp(name, "et_RunFrame")) { assert(args == 1); frame_hooks++; }
    if (!strcmp(name, "et.IPCSend")) {
        assert(args == 2 && results == 0); deliveries++;
        received_sender = vm->L->last_integer; received_message = vm->L->message;
        /* Successful callback deliberately makes NO durable/application ack. */
    }
    return callback_ok;
}
static void G_LuaShutdown(void) {
    unloads++; for (int i = 0; i < LUA_NUM_VM; i++) lVM[i] = NULL;
}
static void G_LuaInit(void) {
    loads++;
    for (int i = 0; i < LUA_NUM_VM; i++) {
        memset(&states[i], 0, sizeof states[i]);
        modules[i] = (lua_vm_t){i, 0, &states[i]}; lVM[i] = &modules[i];
    }
}

/* EXTRACTED_ENGINE_FUNCTIONS */

int main(void) {
    G_LuaInit();
    G_LuaHook_InitGame(5000, 42, 0);
    assert(states[0].integers[0] == 5000 && states[0].integers[1] == 42 && states[0].integers[2] == 0);
    printf("qagame_init %d %d\n", loads, init_hooks);
    G_LuaRestart();
    G_LuaHook_RunFrame(5100);
    printf("lua_reload %d %d %d %d %d\n", loads, unloads, init_hooks, shutdown_hooks, frame_hooks);
    G_LuaHook_ShutdownGame(1);
    G_LuaShutdown(); G_LuaInit(); G_LuaHook_InitGame(5200, 42, 1);
    printf("qagame_restart %d %d %d\n", init_hooks, shutdown_hooks, states[0].integers[2]);

    for (int half = 0; half < 2; half++) {
        for (int defended = 0; defended < 2; defended++) {
            g_currentRound.integer = half; defender = 0; winner = defended ? 0 : 1;
            written_round = -1; finish_stopwatch();
            printf("half %d %d %d %d\n", half, defended, written_round, g_currentRound.integer);
        }
    }
    printf("xp %d\n", xp_calls);
    states[0].target = 1; states[0].message = "identity-ticket";
    assert(_et_IPCSend(&states[0]) == 1);
    printf("ipc_ok %d %d %d %d %d\n", states[0].last_integer, deliveries,
           application_acks, received_sender, !strcmp(received_message, "identity-ticket"));
    callback_present = 0; _et_IPCSend(&states[0]);
    printf("ipc_missing %d %d\n", states[0].last_integer, deliveries);
    callback_present = 1; callback_ok = 0; _et_IPCSend(&states[0]);
    printf("ipc_error %d %d\n", states[0].last_integer, deliveries);
    callback_ok = 1; modules[1].err = 1; _et_IPCSend(&states[0]);
    printf("ipc_errored_vm %d %d\n", states[0].last_integer, deliveries);
    modules[1].err = 0;
    lua_State unknown = {.target=1, .message="unknown-sender"};
    _et_IPCSend(&unknown);
    printf("ipc_unknown_sender %d %d %d\n", unknown.last_integer, received_nil_sender, received_sender);
    lVM[1] = NULL; _et_IPCSend(&states[0]);
    printf("ipc_missing_vm %d %d\n", states[0].last_integer, deliveries);
    return 0;
}
