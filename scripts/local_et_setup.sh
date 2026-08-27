#!/usr/bin/env bash
# =============================================================================
# local_et_setup.sh — ENKRATNA postavitev lokalnega ET:Legacy test serverja
#
# Zakaj: Lua skripte se doslej testirajo na PRODUKCIJSKEM serverju (puran) prek
# `slomix_rcon.py testmode on`. Ta skripta postavi lokalno, binarno identično
# kopijo, da se Lua testira brez tveganja za produkcijo.
#
# Uporaba (owner, enkrat):
#     sudo bash scripts/local_et_setup.sh
#
# Idempotentna: ponovni zagon posodobi kopijo in ne pokvari ničesar.
# Vsakodnevno krmiljenje potem teče BREZ sudo prek scripts/local_et.sh.
#
# Runbook in "delta lista" razlik proti puranu: docs/LOCAL_ET_SERVER.md
# =============================================================================
set -euo pipefail

# ----------------------------- nastavitve ------------------------------------
DEV_USER="${DEV_USER:-samba}"                      # uporabnik, ki poganja agente
ET_USER="et"                                       # uporabnik igralnega serverja
CONSOLE_GROUP="etconsole"                          # skupina za dostop do konzole

PURAN_HOST="puran.hehe.si"
PURAN_PORT="48101"
PURAN_KEY="/home/${DEV_USER}/.ssh/etlegacy_bot"
PURAN_GAME_DIR="/home/et/etlegacy-v2.83.1-x86_64"

# Ime mape se NAMERNO ne spreminja (puran je na v2.84.0, mapa pa se še vedno
# imenuje 2.83.1) — trdo je kodirano v bot/cogs/server_control.py:171.
GAME_DIR="/home/et/etlegacy-v2.83.1-x86_64"
HOME_PATH="/home/et/.etlegacy/legacy"
CONSOLE_SOCK="/home/et/.et-console.sock"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_PUBKEY="/home/${DEV_USER}/.ssh/etlegacy_local.pub"

SSH_OPTS=(-p "${PURAN_PORT}" -i "${PURAN_KEY}" -o BatchMode=yes
          -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
          -o LogLevel=ERROR)

# ----------------------------- pomožno ---------------------------------------
step() { echo; echo "==> $*"; }
ok()   { echo "    ✅ $*"; }
warn() { echo "    ⚠️  $*"; }
die()  { echo "    ❌ $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Zaženi z: sudo bash scripts/local_et_setup.sh"
[ -f "${PURAN_KEY}" ] || die "Ni SSH ključa za puran: ${PURAN_KEY}"
[ -f "${LOCAL_PUBKEY}" ] || die "Ni lokalnega javnega ključa: ${LOCAL_PUBKEY}
   Ustvari ga kot ${DEV_USER}: ssh-keygen -t ed25519 -f ~/.ssh/etlegacy_local -N ''"
[ -f "${REPO_DIR}/server/local/local.cfg" ] || die "Manjka ${REPO_DIR}/server/local/local.cfg"

# ----------------------------------------------------------------------------
step "0/8  Odvisnosti"
# Isti nabor, kot ga namesti freshinstall.sh (iamez/etlegacy-scripts) — `curl`
# je obvezen, ker ga stats_discord_webhook.lua kliče za pošiljanje na Discord.
MISSING=()
for c in curl unzip tmux rsync scp sha256sum lua5.4 luac5.4; do
    command -v "$c" >/dev/null || MISSING+=("$c")
done
if [ ${#MISSING[@]} -gt 0 ]; then
    warn "manjka: ${MISSING[*]}"
    apt-get install -y curl unzip tmux rsync openssh-client lua5.4 || \
        die "namestitev odvisnosti ni uspela"
fi
ok "vse odvisnosti so na voljo"

# ----------------------------------------------------------------------------
step "1/8  Uporabnik ${ET_USER} in skupina ${CONSOLE_GROUP}"
if id "${ET_USER}" &>/dev/null; then
    ok "uporabnik ${ET_USER} že obstaja"
else
    useradd -m -s /bin/bash "${ET_USER}"
    ok "uporabnik ${ET_USER} ustvarjen (/home/${ET_USER})"
fi

if getent group "${CONSOLE_GROUP}" &>/dev/null; then
    ok "skupina ${CONSOLE_GROUP} že obstaja"
else
    groupadd "${CONSOLE_GROUP}"
    ok "skupina ${CONSOLE_GROUP} ustvarjena"
fi
usermod -aG "${CONSOLE_GROUP}" "${ET_USER}"
usermod -aG "${CONSOLE_GROUP}" "${DEV_USER}"
ok "${ET_USER} in ${DEV_USER} sta v skupini ${CONSOLE_GROUP}"

# ----------------------------------------------------------------------------
step "2/8  SSH dostop za bota (localhost → et)"
install -d -m 700 -o "${ET_USER}" -g "${ET_USER}" "/home/${ET_USER}/.ssh"
AUTH="/home/${ET_USER}/.ssh/authorized_keys"
touch "${AUTH}"
if grep -qF "$(cut -d' ' -f2 "${LOCAL_PUBKEY}")" "${AUTH}" 2>/dev/null; then
    ok "javni ključ je že v authorized_keys"
else
    cat "${LOCAL_PUBKEY}" >> "${AUTH}"
    ok "javni ključ dodan v authorized_keys"
fi
chown "${ET_USER}:${ET_USER}" "${AUTH}"
chmod 600 "${AUTH}"

# ----------------------------------------------------------------------------
step "3/8  Paritetna kopija game dira s purana (~766 MB, traja nekaj minut)"
install -d -o "${ET_USER}" -g "${ET_USER}" "${GAME_DIR}"
# Preverjeno 17. 8. 2026: Lua datoteke same vsebujejo le placeholderje
# (WEBHOOK_ID/PROD_ID); pravi Discord URL živi izključno v
# stats_discord_webhook_config.lua. Kljub temu ga izključimo eksplicitno, da
# ostane res tako tudi, če ga kdo kdaj odloži v basepath.
# tar prek ssh, NE rsync: puran rsync-a NIMA (preverjeno 17. 8. —
# `command -v rsync` → nič), tar pa je povsod. Izključitve so iste kot v
# prejšnji rsync različici. Idempotentno: tar -x povozi obstoječe datoteke,
# ničesar ne briše (namerno — nikoli --delete semantike).
ssh "${SSH_OPTS[@]}" "et@${PURAN_HOST}" \
    "cd '${PURAN_GAME_DIR}' && tar -cf - \
        --exclude='*.bak' --exclude='*.bak_*' --exclude='*.bak-*' \
        --exclude='*.old' --exclude='*.predeploy_*' --exclude='*.claude' \
        --exclude='*.log' --exclude='backups' \
        --exclude='stats_discord_webhook_config.lua' ." \
    | tar -xf - -C "${GAME_DIR}"
chown -R "${ET_USER}:${ET_USER}" "${GAME_DIR}"
ok "game dir kopiran: $(du -sh "${GAME_DIR}" | cut -f1)"

# ----------------------------------------------------------------------------
step "4/8  Homepath (selektivno — NIKOLI cel homepath s purana)"
# Skupina je etconsole, da agenti (uporabnik ${DEV_USER}) berejo etconsole.log
# in nastale stats datoteke brez sudo.
install -d -m 750 -o "${ET_USER}" -g "${CONSOLE_GROUP}" "/home/${ET_USER}/.etlegacy"
install -d -m 750 -o "${ET_USER}" -g "${CONSOLE_GROUP}" "${HOME_PATH}"
for d in gamestats gametimes proximity luascripts session; do
    install -d -m 750 -o "${ET_USER}" -g "${CONSOLE_GROUP}" "${HOME_PATH}/${d}"
done
ok "mape ustvarjene pod ${HOME_PATH} (skupina ${CONSOLE_GROUP}, berljivo)"

# Živi stats_discord_webhook.lua je na puranu v HOMEPATH (povozi basepath).
# Kopiramo samo to in live_events_config.lua. NE kopiramo:
#   stats_discord_webhook_config.lua  (produkcijski Discord webhook URL)
#   sv_protect.log                    (IP-ji igralcev)
#   legacy3.log / etconsole.log       (159 MB zgodovine, prepisan ob zagonu)
for f in stats_discord_webhook.lua live_events_config.lua; do
    # ssh+cat, ne scp: SSH_OPTS nosi `-p <port>` za ssh, scp pa vrata bere iz
    # `-P` — z `-p` je scp tiho ciljal privzeta vrata in oba prenosa sta padla
    # (ujeto ob prvem zagonu 17. 8.).
    if ssh "${SSH_OPTS[@]}" "et@${PURAN_HOST}" \
        "cat '/home/et/.etlegacy/legacy/luascripts/${f}'" \
        > "${HOME_PATH}/luascripts/${f}" 2>/dev/null \
        && [ -s "${HOME_PATH}/luascripts/${f}" ]; then
        chown "${ET_USER}:${ET_USER}" "${HOME_PATH}/luascripts/${f}"
        ok "homepath: ${f}"
    else
        warn "homepath: ${f} ni bilo mogoče kopirati (morda ga na puranu ni)"
    fi
done
warn "stats_discord_webhook_config.lua NAMERNO ni kopiran — brez njega Lua
       le opozori in NE pošilja na Discord (varno privzeto stanje)."

# ----------------------------------------------------------------------------
step "5/8  Lokalni config etmain/local.cfg"
install -m 644 -o "${ET_USER}" -g "${ET_USER}" \
    "${REPO_DIR}/server/local/local.cfg" "${GAME_DIR}/etmain/local.cfg"
ok "local.cfg nameščen"

# ----------------------------------------------------------------------------
step "6/8  Omni-bot: boti naj igrajo tudi na praznem serverju"
OMNI_CFG="${GAME_DIR}/legacy/omni-bot/et/user/omni-bot.cfg"
if [ -f "${OMNI_CFG}" ]; then
    # SleepBots=1 (privzeto na puranu) uspava bote, ko ni ljudi — server_manager.gm
    # CheckSleep() kliče bot.Enable(false) ob NumPlayers == NumBots.
    # SaveConfigChanges=1 pomeni, da omni-bot ob izklopu datoteko prepiše in
    # nastavitev tiho izgine — zato ga tudi ugasnemo.
    sed -i 's/^SleepBots .*/SleepBots                      = 0/;
            s/^SaveConfigChanges .*/SaveConfigChanges              = 0/' "${OMNI_CFG}"
    ok "SleepBots=0, SaveConfigChanges=0"
    grep -E '^(SleepBots|SaveConfigChanges|MinBots|MaxBots)' "${OMNI_CFG}" | sed 's/^/    /'
else
    warn "ni ${OMNI_CFG} — preveri, ali je rsync prinesel omni-bot"
fi

# ----------------------------------------------------------------------------
step "7/8  tmux konzolna seja (skupni socket)"
# Seja teče pod et in vsebuje navadno bash lupino; server se v njej zaganja in
# ustavlja prek send-keys, zato agenti za start/stop NE potrebujejo sudo.
if sudo -u "${ET_USER}" tmux -S "${CONSOLE_SOCK}" has-session -t etlocal 2>/dev/null; then
    ok "tmux seja 'etlocal' že teče"
else
    sudo -u "${ET_USER}" tmux -S "${CONSOLE_SOCK}" new-session -d -s etlocal -c "${GAME_DIR}"
    ok "tmux seja 'etlocal' ustvarjena"
fi
chgrp "${CONSOLE_GROUP}" "${CONSOLE_SOCK}"
chmod 660 "${CONSOLE_SOCK}"
# Skupina mora imeti pravico vstopa v /home/et, da doseže socket:
chmod 750 "/home/${ET_USER}"
chgrp "${CONSOLE_GROUP}" "/home/${ET_USER}"
ok "socket ${CONSOLE_SOCK} dostopen skupini ${CONSOLE_GROUP}"

# ----------------------------------------------------------------------------
step "8/8  sudoers: dovoli ponovni zagon tmux seje brez gesla (po rebootu)"
# Ozko pravilo: samo tmux na TEM socketu, samo pod uporabnikom et. `et` je
# neprivilegiran uporabnik, ustvarjen izključno za testni igralni server.
SUDOERS_FILE="/etc/sudoers.d/local-et-console"
cat > "${SUDOERS_FILE}" <<EOF
# Lokalni ET:Legacy test server — zagon konzolne tmux seje brez gesla.
# Postavljeno s scripts/local_et_setup.sh. Odstrani z: rm ${SUDOERS_FILE}
${DEV_USER} ALL=(${ET_USER}) NOPASSWD: /usr/bin/tmux -S ${CONSOLE_SOCK} *
EOF
chmod 440 "${SUDOERS_FILE}"
if visudo -cf "${SUDOERS_FILE}" >/dev/null; then
    ok "sudoers pravilo nameščeno (${SUDOERS_FILE})"
else
    rm -f "${SUDOERS_FILE}"
    die "sudoers pravilo ni veljavno — odstranjeno"
fi

# ----------------------------------------------------------------------------
echo
echo "============================================================"
echo " Postavitev končana."
echo
echo " Preveri pariteto in zaženi:"
echo "     scripts/local_et.sh parity     # sha256 proti puranu"
echo "     scripts/local_et.sh start"
echo "     scripts/local_et.sh verify"
echo
echo " OPOMBA: ${DEV_USER} je bil dodan v skupino ${CONSOLE_GROUP}. Nova"
echo " članstva v skupinah veljajo šele v NOVI prijavi — če scripts/local_et.sh"
echo " javi 'permission denied' na socketu, se odjavi in prijavi (ali 'newgrp"
echo " ${CONSOLE_GROUP}')."
echo "============================================================"
