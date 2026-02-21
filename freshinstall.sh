#!/bin/bash

#Script that will install two servers into screen "aim" and "vektor"
#servers are preconfigured to my personal servers, one scrim/match server and one warmup/practice server
#match server configuration by vektor


DOMA="/home/et"
GAME_DIR="/home/et/etlegacy-v2.81.1-x86_64"
ETMAIN_DIR="/home/et/etlegacy-v2.81.1-x86_64/etmain"
CONFIG_DIR="/home/et/etlegacy-v2.81.1-x86_64/etmain/configs"
LEGACY_DIR="/home/et/etlegacy-v2.81.1-x86_64/legacy"


# Update package index and upgrade packages
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies necessary to run the latest legacy version
sudo apt-get install sudo openssh-server curl unzip screen dos2unix -y

# Install Fail2ban and configure to guard SSH port (which is listening on 48101)
sudo apt-get install fail2ban -y
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo sed -i 's/\(port\s*=\s*\)ssh/\148101/' /etc/fail2ban/jail.local
sudo systemctl restart fail2ban.service

# Update the SSH configuration file to use the new port
#sudo sed -i 's/Port 22/Port 48101/g' /etc/ssh/sshd_config
sudo sed -i -e 's/#Port 22/Port 48101/g' -e 's/Port 22/Port 48101/g' /etc/ssh/sshd_config


# Create user 'et' and set default shell to bash
sudo useradd -m -s /bin/bash et
password=$(openssl rand -base64 12)
sudo usermod -aG sudo et
sudo chown -R et:et /home/et
echo "et:$password" | sudo chpasswd

#setup directories and set permissions
sudo -u et mkdir /home/et/etlegacy-v2.81.1-x86_64
sudo -u et mkdir /home/et/etlegacy-v2.81.1-x86_64/etmain
sudo -u et mkdir /home/et/etlegacy-v2.81.1-x86_64/etmain/configs
sudo -u et mkdir /home/et/etlegacy-v2.81.1-x86_64/legacy

sudo chmod 700 /home/et
sudo chmod 700 /home/et/etlegacy-v2.81.1-x86_64
sudo chmod 700 /home/et/etlegacy-v2.81.1-x86_64/etmain
sudo chmod 700 /home/et/etlegacy-v2.81.1-x86_64/etmain/configs
sudo chmod 700 /home/et/etlegacy-v2.81.1-x86_64/legacy


#download etlegacy server installation script
sudo curl -o /home/et/etlegacy-v2.81.1-x86_64.sh https://www.etlegacy.com/download/file/552
sudo chown et:et /home/et/etlegacy-v2.81.1-x86_64.sh
sudo chmod a+x /home/et/etlegacy-v2.81.1-x86_64.sh


#install the server using defaults and as ET user
yes | sudo -H -u et /bin/bash -c 'cd /home/et/ && ./etlegacy-v2.81.1-x86_64.sh'

# Set ownership and permissions for extracted files
sudo chown -R et:et /home/et/etlegacy-v2.81.1-x86_64/
sudo chmod -R 700 /home/et/etlegacy-v2.81.1-x86_64/

# Download competitive configs from ET: Legacy Competitive GitHub repository Extract the contents of the archive Copy the contents to $ETMAIN_DIR
sudo wget -q "https://github.com/ET-Legacy-Competitive/Legacy-Competition-League-Configs/archive/main.zip" -O "/tmp/main.zip"
sudo unzip -q "/tmp/main.zip" -d "/tmp/"
sudo cp -r "/tmp/Legacy-Competition-League-Configs-main/." "$ETMAIN_DIR"
sudo chown -R et:et "$ETMAIN_DIR"
sudo chmod -R 700 "$ETMAIN_DIR"
sudo rm -rf "/tmp/Legacy-Competition-League-Configs-main"

# Additional commands to set ownership and permissions for the server
chown -R et:et "$CONFIG_DIR"
chown -R et:et "$ETMAIN_DIR"
chmod 700 "$ETMAIN_DIR"
chmod 700 "$LEGACY_DIR"
chown -R et:et "$DOMA"

# Download server configs
sudo -u et curl -sSfL "https://raw.githubusercontent.com/iamez/freshinstall/main/aim.cfg" -o "$ETMAIN_DIR/aim.cfg"
chown et:et "$ETMAIN_DIR/aim.cfg"
chmod 700 "$ETMAIN_DIR/aim.cfg"
sudo -u et curl -sSfL "https://raw.githubusercontent.com/iamez/freshinstall/main/aim.config" -o "$CONFIG_DIR/aim.config"
chown et:et "$CONFIG_DIR/aim.config"
chmod 700 "$CONFIG_DIR/aim.config"
sudo -u et curl -sSfL "https://raw.githubusercontent.com/iamez/freshinstall/main/vektor.cfg" -o "$ETMAIN_DIR/vektor.cfg"
chown et:et "$ETMAIN_DIR/vektor.cfg"
chmod 700 "$ETMAIN_DIR/vektor.cfg"
echo "Custom configs have been successfully downloaded and installed."


# Create the abs1.3.lua script for aim server
ABS_LUA_FILE="${LEGACY_DIR}/abs1.3.lua"
echo 'local version = 1.3
local modname = "abs"

function getTeam(clientNum)
    return et.gentity_get(clientNum, "sess.sessionTeam")
end

-- callbacks
function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)
end

function et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
    et.gentity_set(clientNum, "ps.powerups", et.PW_NOFATIGUE, 1)
    et.gentity_set(clientNum, "health", 10000)
    if getTeam(clientNum) == 1 then
        et.AddWeaponToPlayer(clientNum, et.WP_MP40, 9999, 9999, 0)
    end
    if getTeam(clientNum) == 2 then
        et.AddWeaponToPlayer(clientNum, et.WP_THOMPSON, 9999, 9999, 0)
    end
end' > "${ABS_LUA_FILE}"
sudo chown et:et "$ABS_LUA_FILE"
sudo chmod a+x "$ABS_LUA_FILE"


# Download etdaemon.sh and move it to the game directory
curl https://raw.githubusercontent.com/iamez/freshinstall/main/etdaemon.sh > "$GAME_DIR/etdaemon.sh"
chmod a+x "$GAME_DIR/etdaemon.sh"
chmod a+x "$ABS_LUA_FILE"
chown et:et "$GAME_DIR/etdaemon.sh"
sed -i -e "s#^GAME_DIR=\".*\"#GAME_DIR=\"$GAME_DIR\"#" -e 's/\r//' "$GAME_DIR/etdaemon.sh"


#Download all "official" competitive maps, and some other popular maps.
files=(
    "aimmap3.pk3"
    "badplace4_beta8.pk3"
    "braundorf_b4.pk3"
    "bremen_b3.pk3"
    "ctf_multi2.pk3"
    "CTF_Multi.pk3"
    "ctf_well.pk3"
    "decay_b7.pk3"
    "decay_sw.pk3"
    "erdenberg_t2.pk3"
    "et_beach.pk3"
    "et_brewdog_b6.pk3"
    "et_headshot2_b2.pk3"
    "et_ice.pk3"
    "etl_adlernest_v4.pk3"
    "etl_frostbite_v17.pk3"
    "etl_ice_v12.pk3"
    "etl_sp_delivery_v5.pk3"
    "etl_supply_v12.pk3"
    "etl_warbell_v3.pk3"
    "et_ufo_final.pk3"
    "Frostbite.pk3"
    "gammajump.pk3"
    "karsiah_te2.pk3"
    "karsiah_te3.pk3"
    "kothet2.pk3"
    "lnatrickjump.pk3"
    "maniacmansion.pk3"
    "missile_b3.pk3"
    "mp_sillyctf.pk3"
    "mp_sub_rc1.pk3"
    "multi_huntplace.pk3"
    "reactor_final.pk3"
    "sos_secret_weapon.pk3"
    "sp_delivery_te.pk3"
    "supply.pk3"
    "sw_battery.pk3"
    "sw_goldrush_te.pk3"
    "sw_oasis_b3.pk3"
    "te_escape2_fixed.pk3"
    "te_escape2.pk3"
    "te_valhalla.pk3"
    "UseMeJump.pk3"
)

num_downloaded=0
num_skipped=0
num_failed=0

for file in "${files[@]}"
do
    if [ -e "${ETMAIN_DIR}/${file}" ]; then
        echo "${file} already exists in ${ETMAIN_DIR} and will be skipped"
        ((num_skipped++))
        continue
    fi

    downloaded=false
    for link in \
        "http://download.hirntot.org/etmain/${file}" \
        "https://et.clan-etc.de/etmain/${file}" \
        "http://www.et-spessartraeuber.de/et/etmain/${file}" \
        "http://www.bunker4fun.com/b4/dl.php?dir=etmain&file=${file}"
    do
        if sudo wget -q "$link" -O "$ETMAIN_DIR/${file}"; then
            downloaded=true
            ((num_downloaded++))
            break
        fi
    done
    if ! $downloaded; then
        echo "${file} not found and skipped"
        ((num_failed++))
        continue
    fi
    sudo chown et:et "${ETMAIN_DIR}/${file}"
    sudo chmod 700 "${ETMAIN_DIR}/${file}"
done

echo "Downloaded ${num_downloaded} files. Skipped ${num_skipped} files that already exist. Failed to download ${num_failed} files"

# Create the start.sh script
cat << EOF > $DOMA/start.sh
#!/bin/bash
sleep 10
cd $GAME_DIR
bash etdaemon.sh &
EOF

# Set permissions for start.sh
sudo chown et:et $DOMA/start.sh
sudo chmod a+x $DOMA/start.sh

# Add crontab entries
(crontab -u et -l ; echo "0 6 * * * kill \$(pidof $GAME_DIR/etlded.x86_64)") | crontab -u et -
(crontab -u et -l ; echo "@reboot /bin/bash $DOMA/start.sh >/dev/null 2>&1") | crontab -u et -

sudo chmod a+x $GAME_DIR/etlded.x86_64
sudo touch /home/et/start_servers.log
sudo chown et:et /home/et/start_servers.log

# Start the server
su - et -s /bin/bash -c "cd /home/et/etlegacy-v2.81.1-x86_64 && dos2unix etdaemon.sh && ./etdaemon.sh" &
#echo "SSH will now listen on 48101 port. Server IP address(es): $(hostname -I)"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Password: $password, SSH Port: 48101, Server IP(s): $(hostname -I)" >> saved.log
echo "Server IP(s): $(hostname -I) SSH LOGIN DETAILS - et:$password , wrote saved.log"

sudo systemctl restart sshd.service
