#!/usr/bin/env bash
# =============================================================================
# local_et.sh — krmiljenje lokalnega ET:Legacy test serverja (dev box)
#
# On-demand: server teče SAMO med testom. Ugasnjen ne porabi ničesar.
# Vse spodaj deluje BREZ sudo — uporabnik mora biti v skupini `etconsole`
# (to uredi scripts/local_et_setup.sh, ki se požene enkrat).
#
#   -v <verzija>         izberi verzijo (privzeto 2.84.0 = obstoječa namestitev)
#   --versions           izpiši znane verzije in njihove poti/porte
#
#   start                zaženi server v tmux seji
#   stop                 ustavi server (konzolni `quit`), tmux seja ostane
#   status               teče? koliko botov? katera mapa?
#   console "<ukaz>"     pošlji ukaz v konzolo in izpiši, kar se je izpisalo
#   rcon "<ukaz>"        isto prek UDP RCON (ista pot kot na puranu)
#   deploy <lua>         namesti Lua na pravo mesto + full map load
#   tail [n]             zadnjih n vrstic konzole (privzeto 40)
#   watch                sledi konzoli v živo (Ctrl-C za izhod)
#   testmode on|off|status   boti + stopwatch rotacija (lokalno = exec local.cfg)
#   verify               so vsi Lua moduli naloženi? so napake?
#   parity               sha256 primerjava s puranom
#   files                kaj je nastalo v gamestats/proximity/gametimes
#   attach               priklopi se v tmux in glej v živo
#
# ⛔ NIKOLI `lua_restart` — c0rnp0rn8 se sesuje. Vedno poln `map <ime>`.
# =============================================================================
set -uo pipefail

ET_USER="et"

# ===== REGISTER VERZIJ =======================================================
# Več verzij hkrati: comp skupnost ni nujno na isti verziji kot razvijalci,
# zato mora Slomix teči na obeh. Vsaka verzija ima SVOJ port, homepath, socket
# in tmux sejo, da lahko tečeta sočasno in se gamestats datoteke ne pomešajo.
#
# ⚠️ Mapa se preslika IZRECNO, ne izpelje iz verzije: mapa
# `etlegacy-v2.83.1-x86_64` vsebuje v resnici v2.84.0. Imena ne preimenujemo
# (trdo je kodirano na štirih mestih), zato tu vodimo resnico — `status` pa
# izpiše verzijo, ki jo javi sam binarij.
declare -A ETL_DIR=(
    [2.84.0]="/home/et/etlegacy-v2.83.1-x86_64"
    [2.85.0]="/home/et/etlegacy-v2.85.0-x86_64"
)
declare -A ETL_HOME_ROOT=(
    [2.84.0]="/home/et/.etlegacy"
    [2.85.0]="/home/et/.etlegacy-v2.85.0"
)
declare -A ETL_TAG=(   [2.84.0]=""      [2.85.0]="285"   )
declare -A ETL_PORT=(  [2.84.0]="27960" [2.85.0]="27961" )

# Privzetek NAMENOMA ostane obstoječa namestitev, da stari ukazi delajo enako.
ETL_VERSION="${ETL_VERSION:-2.84.0}"

# Vodilne izbire (-v <verzija>) pred podukazom.
while [ $# -gt 0 ]; do
    case "${1}" in
        -v|--version) ETL_VERSION="${2:-}"; shift 2 ;;
        --versions)
            echo "Znane verzije:"
            for v in "${!ETL_DIR[@]}"; do
                printf "  %-8s dir=%s port=%s\n" "${v}" "${ETL_DIR[$v]}" "${ETL_PORT[$v]}"
            done | sort
            exit 0 ;;
        *) break ;;
    esac
done

[ -n "${ETL_DIR[$ETL_VERSION]:-}" ] || {
    echo "❌ Neznana verzija '${ETL_VERSION}'. Znane: ${!ETL_DIR[*]}" >&2
    echo "   (seznam s potmi: $0 --versions)" >&2
    exit 1
}

GAME_DIR="${ETL_DIR[$ETL_VERSION]}"
FS_HOMEPATH="${ETL_HOME_ROOT[$ETL_VERSION]}"
TAG="${ETL_TAG[$ETL_VERSION]}"
RCON_PORT_V="${ETL_PORT[$ETL_VERSION]}"
HOME_PATH="${FS_HOMEPATH}/legacy"
CONSOLE_LOG="${HOME_PATH}/etconsole.log"
CONSOLE_SOCK="/home/et/.et-console${TAG:+-${TAG}}.sock"
TMUX_SESSION="etlocal${TAG}"

LOCAL_KEY="${LOCAL_ET_KEY:-$HOME/.ssh/etlegacy_local}"
RCON_PW="${LOCAL_ET_RCON_PW:-slomixlocal}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PURAN="etlegacy-server"          # ~/.ssh/config alias
PURAN_GAME_DIR="/home/et/etlegacy-v2.83.1-x86_64"

TM=(tmux -S "${CONSOLE_SOCK}")
SCP_OPTS=(-i "${LOCAL_KEY}" -P 22 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

die()  { echo "❌ $*" >&2; exit 1; }
info() { echo "→  $*"; }

# Loči verziji, ki tečeta hkrati — sicer bi `pgrep -f etlded.x86_64` vrnil
# kateregakoli od njiju. Razločevalec je fs_homepath, ne pot mape: strežnik se
# zažene z `cd $GAME_DIR && ./etlded.x86_64`, zato v ukazni vrstici polne poti
# SPLOH NI (preverjeno proti živemu procesu). fs_homepath pa je vedno tam in je
# na verzijo enoličen.
server_pid() {
    local re; re="$(printf '%s' "${FS_HOMEPATH}" | sed 's/[.[\*^$]/\\&/g')"
    pgrep -u "${ET_USER}" -f "etlded\.x86_64.*fs_homepath ${re}( |\$)" | head -1
}

require_session() {
    [ -S "${CONSOLE_SOCK}" ] || die "Ni konzolnega socketa (${CONSOLE_SOCK}).
   Postavitev še ni tekla: sudo bash scripts/local_et_setup.sh"
    "${TM[@]}" has-session -t "${TMUX_SESSION}" 2>/dev/null || die \
"tmux seja '${TMUX_SESSION}' ne teče. Znova jo zaženi z:
   sudo -u ${ET_USER} tmux -S ${CONSOLE_SOCK} new-session -d -s ${TMUX_SESSION} -c ${GAME_DIR}"
}

require_running() {
    [ -n "$(server_pid)" ] || die "Server ne teče. Zaženi ga s: $0 start"
}

# Pošlje ukaz v konzolo in izpiše natanko tisto, kar se je zaradi njega izpisalo:
# zabeleži velikost etconsole.log PREJ, pošlje, počaka, izpiše od offseta naprej.
# Zanesljivejše od `capture-pane`, ki vidi le trenutno vidno okno, in ujame tudi
# izpise, ki pridejo z zamikom (npr. Lua napaka nekaj sekund kasneje).
send_console() {
    local cmd="$1" wait="${2:-1.5}" before=0
    [ -f "${CONSOLE_LOG}" ] && before=$(stat -c%s "${CONSOLE_LOG}")
    "${TM[@]}" send-keys -t "${TMUX_SESSION}" "${cmd}" Enter || die "send-keys ni uspel"
    sleep "${wait}"
    if [ -f "${CONSOLE_LOG}" ]; then
        tail -c "+$((before + 1))" "${CONSOLE_LOG}" | grep -av '^$' || true
    fi
}

# ----------------------------------------------------------------------------
cmd_start() {
    require_session
    if [ -n "$(server_pid)" ]; then
        info "Server že teče (PID $(server_pid))."; return 0
    fi
    info "Zaganjam ET:Legacy (dedicated 1 = LAN, brez objave na master seznamu)…"
    "${TM[@]}" send-keys -t "${TMUX_SESSION}" \
        "cd ${GAME_DIR} && ./etlded.x86_64 +set fs_homepath ${FS_HOMEPATH} +set net_port ${RCON_PORT_V} +set dedicated 1 +exec local.cfg" Enter
    for _ in $(seq 1 20); do
        sleep 1
        [ -n "$(server_pid)" ] && { info "Teče (PID $(server_pid))."; sleep 4; cmd_verify; return 0; }
    done
    die "Server se ni zagnal — poglej: $0 tail 60"
}

cmd_stop() {
    require_session
    if [ -z "$(server_pid)" ]; then info "Server ne teče."; return 0; fi
    info "Ustavljam (konzolni 'quit')…"
    "${TM[@]}" send-keys -t "${TMUX_SESSION}" "quit" Enter
    for _ in $(seq 1 15); do
        sleep 1
        [ -z "$(server_pid)" ] && { info "Ustavljen. tmux seja ostaja."; return 0; }
    done
    die "Se ni ustavil. Ročno: kill \$(pgrep -u ${ET_USER} -f etlded.x86_64)"
}

# Verzija, ki jo javi SAM BINARIJ. Ime mape ni dokaz: `etlegacy-v2.83.1-x86_64`
# vsebuje v2.84.0 in prav to neujemanje je že zavajalo.
binary_version() {
    # `grep -m1` zapre cev, strings dobi SIGPIPE in pod `set -o pipefail` je
    # izhod cevi nenicelni TUDI ob najdenem zadetku — brez tega se izpiseta
    # verzija IN "neznana".
    local v
    set +o pipefail
    v="$(strings -a "${GAME_DIR}/etlded.x86_64" 2>/dev/null | grep -m1 -E 'ET Legacy v[0-9]+\.[0-9]+')"
    set -o pipefail
    echo "${v:-neznana}"
}

cmd_status() {
    local pid; pid="$(server_pid)"
    echo "Verzija: ${ETL_VERSION}  (binarij javlja: $(binary_version))"
    echo "Mapa:    ${GAME_DIR}"
    echo "Homepath:${FS_HOMEPATH}   Port: ${RCON_PORT_V}"
    if [ -z "${pid}" ]; then
        echo "Server:  ⚫ ugasnjen"
        [ -S "${CONSOLE_SOCK}" ] && echo "Konzola: ✅ tmux socket pripravljen" \
                                 || echo "Konzola: ❌ socket manjka (poženi setup)"
        return 0
    fi
    echo "Server:  🟢 teče (PID ${pid}, RSS $(ps -o rss= -p "${pid}" | tr -d ' ') kB)"
    echo "Konzola: tmux -S ${CONSOLE_SOCK} attach -t ${TMUX_SESSION}"
    echo
    cmd_rcon "status"
}

cmd_console() {
    [ $# -ge 1 ] || die "Uporaba: $0 console \"<ukaz>\""
    require_session; require_running
    send_console "$*"
}

cmd_rcon() {
    [ $# -ge 1 ] || die "Uporaba: $0 rcon \"<ukaz>\""
    RCON_HOST=127.0.0.1 RCON_PORT="${RCON_PORT_V}" RCON_PASSWORD="${RCON_PW}" \
        python3 "${REPO_DIR}/tools/slomix_rcon.py" cmd "$@"
}

# Kam gre katera Lua datoteka — natanko tako, kot je živo na puranu
# (homepath povozi basepath, zato je pomembno, da ne zgrešimo poti).
lua_target() {
    case "$(basename "$1")" in
        stats_discord_webhook.lua) echo "${HOME_PATH}/luascripts/" ;;
        c0rnp0rn8.lua|endstats.lua) echo "${GAME_DIR}/legacy/" ;;
        proximity_tracker.lua|live_events.lua|team-lock.lua) echo "${GAME_DIR}/legacy/luascripts/" ;;
        dots_arena_1v1.lua) echo "${GAME_DIR}/legacy/luascripts/" ;;
        *) echo "" ;;
    esac
}

cmd_deploy() {
    local src="${1:-}"
    [ -f "${src}" ] || die "Uporaba: $0 deploy <pot-do-lua-datoteke>"
    local dst; dst="$(lua_target "${src}")"
    [ -n "${dst}" ] || die "Ne vem, kam sodi $(basename "${src}").
   Znane: stats_discord_webhook.lua, c0rnp0rn8.lua, endstats.lua,
          proximity_tracker.lua, live_events.lua, team-lock.lua,
          dots_arena_1v1.lua"

    info "Parse gate (luac5.4 -p) …"
    luac5.4 -p "${src}" || die "Lua se ne prevede — deploy prekinjen."
    echo "    ✅ sintaksa OK"

    info "Kopiram → ${dst}"
    scp "${SCP_OPTS[@]}" -q "${src}" "${ET_USER}@127.0.0.1:${dst}" \
        || die "scp ni uspel (je ključ ${LOCAL_KEY} v authorized_keys?)"
    echo "    ✅ $(sha256sum "${src}" | cut -c1-16)…  $(basename "${src}")"

    if [ -n "$(server_pid)" ]; then
        info "Full map load (NIKOLI lua_restart) …"
        send_console "map supply" 8 | tail -20
    else
        info "Server ne teče — Lua se naloži ob naslednjem zagonu."
    fi
}

cmd_tail()  { tail -n "${1:-40}" "${CONSOLE_LOG}" 2>/dev/null || die "Ni ${CONSOLE_LOG}"; }
cmd_watch() { tail -f "${CONSOLE_LOG}"; }

cmd_verify() {
    [ -f "${CONSOLE_LOG}" ] || die "Ni ${CONSOLE_LOG} — server še ni tekel."
    echo "── Naloženi Lua moduli ────────────────────────────────"
    local loaded
    loaded=$(grep -a "loaded into Lua VM" "${CONSOLE_LOG}" | tail -10)
    # shellcheck disable=SC2001 # multiline prefix: ${var//} cannot anchor per-line ^
    [ -n "${loaded}" ] && echo "${loaded}" | sed 's/^/  /' || echo "  (nobenega!)"
    local n; n=$(grep -ac "loaded into Lua VM" "${CONSOLE_LOG}")
    echo
    if [ "${n}" -ge 6 ]; then echo "  ✅ ${n} nalaganj (pričakovanih 6 na zagon)"
    else echo "  ⚠️  samo ${n} nalaganj — pričakovanih 6"; fi

    echo
    echo "── Lua napake ─────────────────────────────────────────"
    local errs
    errs=$(grep -aiE "error running lua|attempt to (index|call|compare|perform)|stack traceback|bad argument" \
           "${CONSOLE_LOG}" | tail -10)
    # shellcheck disable=SC2001 # multiline prefix, same as above
    if [ -n "${errs}" ]; then echo "${errs}" | sed 's/^/  ❌ /'
    else echo "  ✅ nobene"; fi
}

cmd_parity() {
    echo "Primerjam lokalno namestitev s puranom (sha256) …"
    echo
    local files=(
        "etlded.x86_64"
        "legacy/qagame.mp.x86_64.so"
        "legacy/legacy_v2.84.0.pk3"
        "legacy/c0rnp0rn8.lua"
        "legacy/endstats.lua"
        "legacy/luascripts/team-lock.lua"
        "legacy/luascripts/proximity_tracker.lua"
        "legacy/luascripts/live_events.lua"
        "etmain/configs/legacy3.config"
        "etmain/configs/legacy3bot.config"
    )
    local remote_sums; remote_sums=$(ssh -o BatchMode=yes "${PURAN}" \
        "cd ${PURAN_GAME_DIR} && sha256sum ${files[*]} 2>/dev/null") \
        || { echo "❌ puran ni dosegljiv"; return 1; }

    local rc=0
    while read -r sum path; do
        local local_sum
        local_sum=$(sha256sum "${GAME_DIR}/${path}" 2>/dev/null | cut -d' ' -f1)
        if [ -z "${local_sum}" ]; then printf '  ❌ MANJKA   %s\n' "${path}"; rc=1
        elif [ "${local_sum}" = "${sum}" ]; then printf '  ✅ enako    %s\n' "${path}"
        else printf '  ⚠️  RAZLIKA %s\n' "${path}"; rc=1; fi
    done <<< "${remote_sums}"

    echo
    echo "Homepath (stats_discord_webhook.lua — tam je živa verzija):"
    local r l
    r=$(ssh -o BatchMode=yes "${PURAN}" \
        "sha256sum /home/et/.etlegacy/legacy/luascripts/stats_discord_webhook.lua 2>/dev/null" | cut -d' ' -f1)
    l=$(sha256sum "${HOME_PATH}/luascripts/stats_discord_webhook.lua" 2>/dev/null | cut -d' ' -f1)
    if [ -n "${r}" ] && [ "${r}" = "${l}" ]; then echo "  ✅ enako"
    else echo "  ⚠️  RAZLIKA (lokalno: ${l:-manjka})"; rc=1; fi
    return ${rc}
}

cmd_files() {
    for d in gamestats proximity gametimes; do
        local n; n=$(ls -1 "${HOME_PATH}/${d}" 2>/dev/null | wc -l)
        echo "── ${d}: ${n} datotek"
        ls -lt "${HOME_PATH}/${d}" 2>/dev/null | head -6 | tail -5 | sed 's/^/   /'
    done
}

# Test mode. Na puranu to opravi `slomix_rcon.py testmode on` (= exec seareal.cfg);
# lokalno je testni config kar local.cfg — vsebuje ISTE bot nastavitve in isto
# stopwatch rotacijo t1..t12, poleg tega pa `rconpassword slomixlocal` in
# com_watchdog 0.
# ⛔ NE uporabljaj seareal.cfg lokalno: postavi sv_hostname "[TEST] purans.only"
# in s tem povozi oznako verzije, ki je edini način, da v seznamu ločiš 2.84 od 2.85.
cmd_testmode() {
    local mode="${1:-status}"
    require_session
    case "${mode}" in
        on)
            require_running
            info "Test mode: exec local.cfg (boti + rotacija t1..t12)"
            send_console "exec local.cfg" 3 | tail -15
            ;;
        off)
            require_running
            info "Ustavljam bote (server ostaja pokonci)"
            for c in "bot MinBots -1" "bot MaxBots -1" "bot BotTeam -1" "set omnibot_enable 0"; do
                send_console "${c}" 1 >/dev/null
            done
            info "Boti izklopljeni."
            ;;
        status)
            require_running
            echo "── Test mode ──────────────────────────────────────────"
            for cv in omnibot_enable g_customConfig sv_hostname g_gametype timelimit; do
                send_console "${cv}" 1 | grep -a "is:" | sed 's/^ *[0-9]* */  /' || true
            done
            local bots
            bots=$(send_console "status" 2 | grep -ac "\[BOT\]" || true)
            echo "  botov v igri: ${bots}"
            ;;
        *) die "Uporaba: $0 [-v <verzija>] testmode <on|off|status>" ;;
    esac
}

cmd_attach() {
    require_session
    echo "Priklop v konzolo. Odklop: Ctrl-B potem D (NE Ctrl-C — to ubije server)."
    exec "${TM[@]}" attach -t "${TMUX_SESSION}"
}

# ----------------------------------------------------------------------------
case "${1:-}" in
    start)   shift; cmd_start "$@" ;;
    stop)    shift; cmd_stop "$@" ;;
    status)  shift; cmd_status "$@" ;;
    console) shift; cmd_console "$@" ;;
    rcon)    shift; cmd_rcon "$@" ;;
    deploy)  shift; cmd_deploy "$@" ;;
    tail)    shift; cmd_tail "$@" ;;
    watch)   shift; cmd_watch "$@" ;;
    verify)  shift; cmd_verify "$@" ;;
    parity)  shift; cmd_parity "$@" ;;
    files)   shift; cmd_files "$@" ;;
    testmode) shift; cmd_testmode "$@" ;;
    attach)  shift; cmd_attach "$@" ;;
    *) sed -n '3,22p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 1 ;;
esac
