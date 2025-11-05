#!/bin/bash
################################################################################
# ET:Legacy Discord Bot - Linux VPS Setup Script
# Automated installation and configuration for Ubuntu/Debian
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration (edit these if needed)
DEPLOY_DIR="/slomix"
REPO_URL="https://github.com/iamez/slomix.git"
REPO_BRANCH="vps-network-migration"
PG_VERSION="16"
PG_USER="etlegacy_user"
PG_PASSWORD="etlegacy_secure_2025"
PG_DATABASE="etlegacy"
SERVICE_USER="${SUDO_USER:-$USER}"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_step() {
    echo -e "${BLUE}${BOLD}▶${NC} ${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

prompt_yes_no() {
    while true; do
        read -p "$(echo -e ${BOLD}$1 [y/n]: ${NC})" yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root or with sudo"
        exit 1
    fi
}

################################################################################
# Main Installation Steps
################################################################################

print_header "ET:Legacy Discord Bot - Linux Setup"

echo -e "${BOLD}This script will:${NC}"
echo "  • Install PostgreSQL $PG_VERSION"
echo "  • Install Python 3 and dependencies"
echo "  • Clone repository to $DEPLOY_DIR"
echo "  • Setup database and import stats"
echo "  • Create systemd service"
echo "  • Start the bot"
echo ""

if ! prompt_yes_no "Continue with installation?"; then
    echo "Installation cancelled."
    exit 0
fi

check_root

# ==================== STEP 1: Update System ====================
print_header "Step 1: Updating System"
print_step "Running apt update..."
apt-get update -qq
print_success "System updated"

# ==================== STEP 2: Install PostgreSQL ====================
print_header "Step 2: Installing PostgreSQL $PG_VERSION"

if command -v psql &> /dev/null; then
    print_warning "PostgreSQL already installed"
    psql --version
else
    print_step "Installing PostgreSQL..."
    apt-get install -y -qq postgresql-$PG_VERSION postgresql-contrib
    print_success "PostgreSQL installed"
fi

# Start PostgreSQL service
systemctl start postgresql
systemctl enable postgresql
print_success "PostgreSQL service started"

# ==================== STEP 3: Install Python & Dependencies ====================
print_header "Step 3: Installing Python and Dependencies"

print_step "Installing Python3, pip, and build tools..."
apt-get install -y -qq python3 python3-pip python3-venv python3-dev
apt-get install -y -qq libpq-dev git curl

python3 --version
print_success "Python and dependencies installed"

# ==================== STEP 4: Setup PostgreSQL Database ====================
print_header "Step 4: Setting up PostgreSQL Database"

print_step "Creating database user: $PG_USER"
sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASSWORD';" 2>/dev/null || print_warning "User already exists"

print_step "Creating database: $PG_DATABASE"
sudo -u postgres psql -c "CREATE DATABASE $PG_DATABASE OWNER $PG_USER;" 2>/dev/null || print_warning "Database already exists"

print_step "Granting privileges..."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $PG_DATABASE TO $PG_USER;"
sudo -u postgres psql -d $PG_DATABASE -c "GRANT ALL ON SCHEMA public TO $PG_USER;"
sudo -u postgres psql -d $PG_DATABASE -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO $PG_USER;"

print_success "Database configured"

# ==================== STEP 5: Clone Repository ====================
print_header "Step 5: Setting up Repository"

if [ -d "$DEPLOY_DIR" ]; then
    print_warning "Directory $DEPLOY_DIR already exists"
    if prompt_yes_no "Update existing repository?"; then
        print_step "Updating repository..."
        cd $DEPLOY_DIR
        sudo -u $SERVICE_USER git fetch origin
        sudo -u $SERVICE_USER git checkout $REPO_BRANCH
        sudo -u $SERVICE_USER git pull origin $REPO_BRANCH
        print_success "Repository updated"
    fi
else
    print_step "Cloning repository..."
    sudo -u $SERVICE_USER git clone -b $REPO_BRANCH $REPO_URL $DEPLOY_DIR
    print_success "Repository cloned"
fi

cd $DEPLOY_DIR
chown -R $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR

# ==================== STEP 6: Setup Python Virtual Environment ====================
print_header "Step 6: Setting up Python Virtual Environment"

print_step "Creating virtual environment..."
sudo -u $SERVICE_USER python3 -m venv $DEPLOY_DIR/venv
print_success "Virtual environment created"

print_step "Installing Python packages..."
sudo -u $SERVICE_USER $DEPLOY_DIR/venv/bin/pip install --upgrade pip setuptools wheel -q
sudo -u $SERVICE_USER $DEPLOY_DIR/venv/bin/pip install discord.py asyncpg matplotlib numpy python-dotenv -q
print_success "Python packages installed"

# ==================== STEP 7: Configure Bot ====================
print_header "Step 7: Configuring Bot"

if [ -f "$DEPLOY_DIR/bot/config.json" ]; then
    print_warning "bot/config.json already exists"
    if ! prompt_yes_no "Overwrite configuration?"; then
        print_warning "Skipping config creation"
    else
        CREATE_CONFIG=true
    fi
else
    CREATE_CONFIG=true
fi

if [ "$CREATE_CONFIG" = true ]; then
    echo ""
    echo -e "${BOLD}Please enter your Discord bot configuration:${NC}"
    echo ""
    
    # Prompt for Discord token
    while true; do
        read -p "$(echo -e ${BOLD}Discord Bot Token: ${NC})" DISCORD_TOKEN
        if [ ! -z "$DISCORD_TOKEN" ]; then
            break
        fi
        print_error "Token cannot be empty"
    done
    
    print_step "Creating bot/config.json..."
    cat > $DEPLOY_DIR/bot/config.json <<EOF
{
  "token": "$DISCORD_TOKEN",
  "database_type": "postgresql",
  "db_config": {
    "host": "localhost",
    "port": 5432,
    "database": "$PG_DATABASE",
    "user": "$PG_USER",
    "password": "$PG_PASSWORD"
  }
}
EOF
    
    chmod 600 $DEPLOY_DIR/bot/config.json
    chown $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR/bot/config.json
    print_success "Configuration created"
fi

# ==================== STEP 8: Import Stats into Database ====================
print_header "Step 8: Importing Stats into Database"

echo -e "${YELLOW}This may take several minutes depending on the number of stats files...${NC}"
echo ""

if prompt_yes_no "Import stats now?"; then
    print_step "Running postgresql_database_manager.py..."
    sudo -u $SERVICE_USER $DEPLOY_DIR/venv/bin/python3 $DEPLOY_DIR/postgresql_database_manager.py
    
    # Check if import was successful
    ROUND_COUNT=$(sudo -u postgres psql -d $PG_DATABASE -t -c "SELECT COUNT(*) FROM rounds;" 2>/dev/null | xargs)
    
    if [ ! -z "$ROUND_COUNT" ] && [ "$ROUND_COUNT" -gt 0 ]; then
        print_success "Database populated with $ROUND_COUNT rounds"
        
        # Show stats summary
        echo ""
        echo -e "${BOLD}Database Summary:${NC}"
        sudo -u postgres psql -d $PG_DATABASE -c "
            SELECT 
                (SELECT COUNT(*) FROM rounds) as rounds,
                (SELECT COUNT(*) FROM player_comprehensive_stats) as player_stats,
                (SELECT COUNT(*) FROM weapon_comprehensive_stats) as weapon_stats,
                (SELECT COUNT(DISTINCT gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL) as gaming_sessions;
        "
    else
        print_warning "No data imported - check stats directory path"
    fi
else
    print_warning "Skipping stats import - you can run it later with:"
    echo "  cd $DEPLOY_DIR && venv/bin/python3 postgresql_database_manager.py"
fi

# ==================== STEP 9: Create Systemd Service ====================
print_header "Step 9: Creating Systemd Service"

print_step "Creating service file..."
cat > /etc/systemd/system/etlegacy-bot.service <<EOF
[Unit]
Description=ET Legacy Discord Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$DEPLOY_DIR
Environment="PATH=$DEPLOY_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$DEPLOY_DIR/venv/bin/python3 $DEPLOY_DIR/bot/ultimate_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=etlegacy-bot

[Install]
WantedBy=multi-user.target
EOF

print_step "Reloading systemd..."
systemctl daemon-reload

print_step "Enabling service..."
systemctl enable etlegacy-bot

print_success "Service created and enabled"

# ==================== STEP 10: Start Bot Service ====================
print_header "Step 10: Starting Bot Service"

if systemctl is-active --quiet etlegacy-bot; then
    print_warning "Service is already running"
    if prompt_yes_no "Restart service?"; then
        systemctl restart etlegacy-bot
        print_success "Service restarted"
    fi
else
    systemctl start etlegacy-bot
    print_success "Service started"
fi

# Wait a moment for service to start
sleep 3

# Check service status
if systemctl is-active --quiet etlegacy-bot; then
    print_success "Bot is running!"
else
    print_error "Bot failed to start - checking logs..."
    journalctl -u etlegacy-bot -n 20 --no-pager
fi

# ==================== Installation Complete ====================
print_header "Installation Complete! 🎉"

echo -e "${BOLD}Service Status:${NC}"
systemctl status etlegacy-bot --no-pager -l | head -20
echo ""

echo -e "${BOLD}Useful Commands:${NC}"
echo "  View logs:      sudo journalctl -u etlegacy-bot -f"
echo "  Restart bot:    sudo systemctl restart etlegacy-bot"
echo "  Stop bot:       sudo systemctl stop etlegacy-bot"
echo "  Service status: sudo systemctl status etlegacy-bot"
echo ""

echo -e "${BOLD}Database Access:${NC}"
echo "  psql -U $PG_USER -d $PG_DATABASE"
echo ""

echo -e "${BOLD}Configuration Files:${NC}"
echo "  Bot config:     $DEPLOY_DIR/bot/config.json"
echo "  Service file:   /etc/systemd/system/etlegacy-bot.service"
echo ""

echo -e "${BOLD}Update Bot:${NC}"
echo "  cd $DEPLOY_DIR"
echo "  git pull origin $REPO_BRANCH"
echo "  sudo systemctl restart etlegacy-bot"
echo ""

echo -e "${BOLD}Re-import Stats (Nuclear Rebuild):${NC}"
echo "  cd $DEPLOY_DIR"
echo "  venv/bin/python3 postgresql_database_manager.py"
echo "  sudo systemctl restart etlegacy-bot"
echo ""

echo -e "${GREEN}${BOLD}✓ Bot is now running on this server!${NC}"
echo -e "${BOLD}Test it in Discord with commands like: !last_session, !stats, !leaderboard${NC}"
echo ""
