#!/bin/bash
################################################################################
# ET:Legacy Discord Bot - Unified Installation Script
# Consolidated from: setup_linux_bot.sh, vps_install.sh, vps_setup.sh, setup_linux_env.sh
################################################################################

set -e  # Exit on error

################################################################################
# Default Configuration
################################################################################

# Script version
VERSION="1.0.0"

# Installation modes
MODE="interactive"  # Can be: interactive, auto, env-only, full
SKIP_POSTGRESQL=false
SKIP_SYSTEMD=false
SKIP_GIT_CLONE=false
SKIP_DB_IMPORT=false
VERBOSE=false

# Default paths and settings
DEPLOY_DIR="/slomix"
REPO_URL="https://github.com/iamez/slomix.git"
REPO_BRANCH="vps-network-migration"
PG_VERSION="16"
PG_USER="etlegacy_user"
PG_PASSWORD=""
PG_DATABASE="etlegacy"
VENV_DIR=".venv"

################################################################################
# Color Codes
################################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

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

print_info() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}ℹ${NC} $1"
    fi
}

prompt_yes_no() {
    if [ "$MODE" = "auto" ]; then
        return 0  # Auto-accept in auto mode
    fi
    while true; do
        read -p "$(echo -e ${BOLD}$1 [y/n]: ${NC})" yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

show_usage() {
    cat << EOF
${BOLD}ET:Legacy Discord Bot - Unified Installation Script v${VERSION}${NC}

${BOLD}USAGE:${NC}
    $0 [OPTIONS]

${BOLD}MODES:${NC}
    --full              Full installation (clone repo + PostgreSQL + systemd)
    --vps               VPS setup (PostgreSQL + systemd, assumes repo exists)
    --env-only          Python environment setup only (no database/systemd)
    --interactive       Interactive mode with prompts (default)
    --auto              Automatic mode with auto-generated passwords

${BOLD}OPTIONS:${NC}
    --skip-postgresql   Skip PostgreSQL installation and setup
    --skip-systemd      Skip systemd service creation
    --skip-git          Skip git repository cloning
    --skip-import       Skip database import step
    --deploy-dir DIR    Installation directory (default: /slomix)
    --repo-url URL      Git repository URL
    --repo-branch NAME  Git branch to use (default: vps-network-migration)
    --pg-user USER      PostgreSQL username (default: etlegacy_user)
    --pg-database DB    PostgreSQL database name (default: etlegacy)
    --venv-dir DIR      Virtual environment directory (default: .venv)
    --verbose           Enable verbose output
    -h, --help          Show this help message

${BOLD}EXAMPLES:${NC}
    # Full automated installation from scratch
    sudo $0 --full --auto

    # Interactive VPS setup (repo already cloned)
    sudo $0 --vps --interactive

    # Environment setup only (no root required)
    $0 --env-only

    # Custom installation directory
    sudo $0 --full --deploy-dir /opt/etlegacy-bot

    # Skip systemd service creation
    sudo $0 --vps --skip-systemd

${BOLD}TYPICAL USE CASES:${NC}
    1. Fresh VPS installation:
       sudo $0 --full --auto

    2. Update existing installation:
       sudo $0 --vps --skip-git --skip-postgresql

    3. Development environment:
       $0 --env-only

EOF
}

version_ge() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

detect_package_manager() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "apt"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v yum >/dev/null 2>&1; then
        echo "yum"
    elif command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    elif command -v zypper >/dev/null 2>&1; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

################################################################################
# Parse Command Line Arguments
################################################################################

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --full)
                MODE="full"
                shift
                ;;
            --vps)
                MODE="vps"
                SKIP_GIT_CLONE=true
                shift
                ;;
            --env-only)
                MODE="env-only"
                SKIP_POSTGRESQL=true
                SKIP_SYSTEMD=true
                SKIP_GIT_CLONE=true
                SKIP_DB_IMPORT=true
                shift
                ;;
            --interactive)
                MODE="interactive"
                shift
                ;;
            --auto)
                MODE="auto"
                shift
                ;;
            --skip-postgresql)
                SKIP_POSTGRESQL=true
                shift
                ;;
            --skip-systemd)
                SKIP_SYSTEMD=true
                shift
                ;;
            --skip-git)
                SKIP_GIT_CLONE=true
                shift
                ;;
            --skip-import)
                SKIP_DB_IMPORT=true
                shift
                ;;
            --deploy-dir)
                DEPLOY_DIR="$2"
                shift 2
                ;;
            --repo-url)
                REPO_URL="$2"
                shift 2
                ;;
            --repo-branch)
                REPO_BRANCH="$2"
                shift 2
                ;;
            --pg-user)
                PG_USER="$2"
                shift 2
                ;;
            --pg-database)
                PG_DATABASE="$2"
                shift 2
                ;;
            --venv-dir)
                VENV_DIR="$2"
                shift 2
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

################################################################################
# Installation Steps
################################################################################

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Detect package manager
    PKG_MGR=$(detect_package_manager)
    if [ "$PKG_MGR" = "unknown" ]; then
        print_error "Could not detect package manager"
        print_error "Supported: apt, dnf, yum, pacman, zypper"
        exit 1
    fi
    print_success "Package manager: $PKG_MGR"
    
    # Check if running as root for certain operations
    if [ "$SKIP_POSTGRESQL" = false ] || [ "$SKIP_SYSTEMD" = false ]; then
        if [[ $EUID -ne 0 ]]; then
            print_error "This installation requires root privileges"
            print_error "Please run with sudo or as root"
            exit 1
        fi
    fi
    
    # Set SERVICE_USER
    if [[ $EUID -eq 0 ]]; then
        SERVICE_USER="${SUDO_USER:-$USER}"
    else
        SERVICE_USER="$USER"
    fi
    print_success "Service user: $SERVICE_USER"
}

update_system() {
    # Skip system update if not running as root or in env-only mode
    if [[ $EUID -ne 0 ]] || [ "$MODE" = "env-only" ]; then
        print_warning "Skipping system update (not running as root or env-only mode)"
        return
    fi
    
    print_header "Updating System"
    print_step "Running package manager update..."
    
    case $PKG_MGR in
        apt)
            apt-get update -qq
            ;;
        dnf)
            dnf check-update -q || true
            ;;
        yum)
            yum check-update -q || true
            ;;
        pacman)
            pacman -Sy --noconfirm
            ;;
        zypper)
            zypper refresh -q
            ;;
    esac
    
    print_success "System updated"
}

install_postgresql() {
    if [ "$SKIP_POSTGRESQL" = true ]; then
        print_warning "Skipping PostgreSQL installation (--skip-postgresql)"
        return
    fi
    
    print_header "Installing PostgreSQL"
    
    if command -v psql &> /dev/null; then
        print_warning "PostgreSQL already installed"
        psql --version
    else
        print_step "Installing PostgreSQL..."
        case $PKG_MGR in
            apt)
                apt-get install -y -qq postgresql postgresql-contrib
                ;;
            dnf|yum)
                $PKG_MGR install -y -q postgresql-server postgresql-contrib
                postgresql-setup --initdb || true
                ;;
            pacman)
                pacman -S --noconfirm postgresql
                su - postgres -c "initdb -D /var/lib/postgres/data" || true
                ;;
            zypper)
                zypper install -y postgresql-server postgresql-contrib
                ;;
        esac
        print_success "PostgreSQL installed"
    fi
    
    # Start and enable PostgreSQL
    systemctl start postgresql 2>/dev/null || true
    systemctl enable postgresql 2>/dev/null || true
    print_success "PostgreSQL service started"
}

install_python() {
    # Skip Python installation if not running as root or in env-only mode
    if [[ $EUID -ne 0 ]] || [ "$MODE" = "env-only" ]; then
        print_warning "Skipping Python installation (not running as root or env-only mode)"
        
        # Check if Python is available
        if command -v python3 >/dev/null 2>&1; then
            python3 --version
            print_success "Python is already available"
        else
            print_error "Python 3 is not installed. Please install it manually."
            exit 1
        fi
        return
    fi
    
    print_header "Installing Python and Dependencies"
    
    print_step "Installing Python3, pip, and build tools..."
    
    case $PKG_MGR in
        apt)
            apt-get install -y -qq python3 python3-pip python3-venv python3-dev libpq-dev git curl
            ;;
        dnf)
            dnf install -y python3 python3-pip python3-devel postgresql-devel git curl
            ;;
        yum)
            yum install -y python3 python3-pip python3-devel postgresql-devel git curl
            ;;
        pacman)
            pacman -S --noconfirm python python-pip git curl postgresql-libs
            ;;
        zypper)
            zypper install -y python3 python3-pip python3-devel postgresql-devel git curl
            ;;
    esac
    
    python3 --version
    print_success "Python and dependencies installed"
}

setup_database() {
    if [ "$SKIP_POSTGRESQL" = true ]; then
        print_warning "Skipping database setup (--skip-postgresql)"
        return
    fi
    
    print_header "Setting up PostgreSQL Database"
    
    # Generate or prompt for password
    if [ "$MODE" = "auto" ] && [ -z "$PG_PASSWORD" ]; then
        PG_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        print_success "Generated secure database password: $PG_PASSWORD"
    elif [ -z "$PG_PASSWORD" ]; then
        echo ""
        echo -e "${BOLD}Enter password for PostgreSQL user '$PG_USER':${NC}"
        read -sp "Password: " PG_PASSWORD
        echo ""
        read -sp "Confirm password: " PG_PASSWORD_CONFIRM
        echo ""
        
        if [ "$PG_PASSWORD" != "$PG_PASSWORD_CONFIRM" ]; then
            print_error "Passwords don't match"
            exit 1
        fi
    fi
    
    # Escape password for SQL
    PG_PASSWORD_ESCAPED="${PG_PASSWORD//\'/\'\'}"
    
    print_step "Creating database user: $PG_USER"
    sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASSWORD_ESCAPED';" 2>/dev/null || print_warning "User already exists"
    
    print_step "Creating database: $PG_DATABASE"
    sudo -u postgres psql -c "CREATE DATABASE $PG_DATABASE OWNER $PG_USER;" 2>/dev/null || print_warning "Database already exists"
    
    print_step "Granting privileges..."
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $PG_DATABASE TO $PG_USER;"
    sudo -u postgres psql -d $PG_DATABASE -c "GRANT ALL ON SCHEMA public TO $PG_USER;"
    sudo -u postgres psql -d $PG_DATABASE -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO $PG_USER;"
    
    print_success "Database configured"
}

clone_repository() {
    if [ "$SKIP_GIT_CLONE" = true ]; then
        print_warning "Skipping repository clone (--skip-git)"
        
        # If not cloning, assume we're in the repo or use current directory
        if [ "$MODE" = "env-only" ]; then
            DEPLOY_DIR="$(pwd)"
            print_info "Using current directory: $DEPLOY_DIR"
        fi
        return
    fi
    
    print_header "Setting up Repository"
    
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
    chown -R $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR 2>/dev/null || true
}

setup_python_venv() {
    print_header "Setting up Python Virtual Environment"
    
    # Determine working directory
    if [ "$MODE" = "env-only" ]; then
        WORK_DIR="$(pwd)"
    else
        WORK_DIR="$DEPLOY_DIR"
    fi
    
    cd "$WORK_DIR"
    
    # Check Python version
    if command -v python3 >/dev/null 2>&1; then
        PY_VER_FULL=$(python3 -V 2>&1 | awk '{print $2}')
        print_info "Python version: $PY_VER_FULL"
        
        if ! version_ge "$PY_VER_FULL" "3.10"; then
            print_warning "Python version is below 3.10, some features may not work"
        fi
    fi
    
    # Handle existing venv
    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists at $VENV_DIR"
        if [ "$MODE" = "env-only" ]; then
            if prompt_yes_no "Remove and recreate virtual environment?"; then
                rm -rf "$VENV_DIR"
                print_info "Removed existing venv"
            else
                print_warning "Keeping existing venv"
                return
            fi
        fi
    fi
    
    if [ ! -d "$VENV_DIR" ]; then
        print_step "Creating virtual environment..."
        if [[ $EUID -eq 0 ]]; then
            sudo -u $SERVICE_USER python3 -m venv "$WORK_DIR/$VENV_DIR"
        else
            python3 -m venv "$VENV_DIR"
        fi
        print_success "Virtual environment created"
    fi
    
    print_step "Installing Python packages..."
    if [[ $EUID -eq 0 ]]; then
        sudo -u $SERVICE_USER "$WORK_DIR/$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel -q
        if [ -f "$WORK_DIR/requirements.txt" ]; then
            sudo -u $SERVICE_USER "$WORK_DIR/$VENV_DIR/bin/pip" install -r "$WORK_DIR/requirements.txt" -q
        else
            # Install core packages
            sudo -u $SERVICE_USER "$WORK_DIR/$VENV_DIR/bin/pip" install discord.py asyncpg matplotlib numpy python-dotenv -q
        fi
    else
        "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel -q
        if [ -f "requirements.txt" ]; then
            "$VENV_DIR/bin/pip" install -r requirements.txt -q
        else
            "$VENV_DIR/bin/pip" install discord.py asyncpg matplotlib numpy python-dotenv -q
        fi
    fi
    print_success "Python packages installed"
}

configure_bot() {
    if [ "$MODE" = "env-only" ]; then
        print_warning "Skipping bot configuration (--env-only mode)"
        return
    fi
    
    print_header "Configuring Bot"
    
    cd "$DEPLOY_DIR"
    
    # Check if configuration already exists
    if [ -f "$DEPLOY_DIR/.env" ]; then
        print_warning ".env already exists"
        if ! prompt_yes_no "Overwrite configuration?"; then
            print_warning "Keeping existing configuration"
            return
        fi
    fi
    
    # Prompt for Discord token
    if [ "$MODE" != "auto" ]; then
        echo ""
        echo -e "${BOLD}Please enter your Discord bot configuration:${NC}"
        echo ""
        
        while true; do
            read -p "$(echo -e ${BOLD}Discord Bot Token: ${NC})" DISCORD_TOKEN
            if [ ! -z "$DISCORD_TOKEN" ]; then
                break
            fi
            print_error "Token cannot be empty"
        done
        
        read -p "$(echo -e ${BOLD}Discord Guild ID \(optional\): ${NC})" GUILD_ID
        read -p "$(echo -e ${BOLD}Stats Channel ID \(optional\): ${NC})" STATS_CHANNEL
    fi
    
    print_step "Creating .env configuration..."
    cat > "$DEPLOY_DIR/.env" <<EOF
# ET:Legacy Discord Bot Configuration
# Auto-generated by install.sh v${VERSION}

# ========== DATABASE CONFIGURATION ==========
DATABASE_TYPE=postgresql

# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=$PG_DATABASE
POSTGRES_USER=$PG_USER
POSTGRES_PASSWORD=$PG_PASSWORD
POSTGRES_MIN_POOL=10
POSTGRES_MAX_POOL=30

# SQLite Configuration (fallback)
SQLITE_DB_PATH=bot/etlegacy_production.db

# ========== DISCORD CONFIGURATION ==========
${DISCORD_TOKEN:+DISCORD_BOT_TOKEN=$DISCORD_TOKEN}
${GUILD_ID:+GUILD_ID=$GUILD_ID}
${STATS_CHANNEL:+STATS_CHANNEL_ID=$STATS_CHANNEL}

# ========== STATS FILE CONFIGURATION ==========
STATS_DIRECTORY=local_stats
BACKUP_DIRECTORY=processed_stats

# ========== AUTOMATION SETTINGS ==========
AUTOMATION_ENABLED=false
LOG_LEVEL=INFO
EOF
    
    chmod 600 "$DEPLOY_DIR/.env"
    chown $SERVICE_USER:$SERVICE_USER "$DEPLOY_DIR/.env" 2>/dev/null || true
    print_success "Configuration created and secured"
}

import_database() {
    if [ "$SKIP_DB_IMPORT" = true ]; then
        print_warning "Skipping database import (--skip-import)"
        return
    fi
    
    if [ "$SKIP_POSTGRESQL" = true ]; then
        return
    fi
    
    print_header "Importing Stats into Database"
    
    cd "$DEPLOY_DIR"
    
    echo -e "${YELLOW}This may take several minutes depending on the number of stats files...${NC}"
    echo ""
    
    if prompt_yes_no "Initialize database schema and import stats now?"; then
        print_step "Running postgresql_database_manager.py..."
        
        if [[ $EUID -eq 0 ]]; then
            sudo -u $SERVICE_USER "$DEPLOY_DIR/$VENV_DIR/bin/python3" "$DEPLOY_DIR/postgresql_database_manager.py" <<EOF
1
EOF
        else
            "$VENV_DIR/bin/python3" postgresql_database_manager.py <<EOF
1
EOF
        fi
        
        # Check if import was successful
        ROUND_COUNT=$(sudo -u postgres psql -d $PG_DATABASE -t -c "SELECT COUNT(*) FROM rounds;" 2>/dev/null | xargs || echo "0")
        
        if [ ! -z "$ROUND_COUNT" ] && [ "$ROUND_COUNT" -gt 0 ]; then
            print_success "Database initialized with schema"
        else
            print_warning "Database schema created, but no data imported yet"
            print_info "You can import data later by running:"
            echo "  cd $DEPLOY_DIR && $VENV_DIR/bin/python3 postgresql_database_manager.py"
        fi
    else
        print_warning "Skipping database import - you can run it later with:"
        echo "  cd $DEPLOY_DIR && $VENV_DIR/bin/python3 postgresql_database_manager.py"
    fi
}

create_systemd_service() {
    if [ "$SKIP_SYSTEMD" = true ]; then
        print_warning "Skipping systemd service creation (--skip-systemd)"
        return
    fi
    
    print_header "Creating Systemd Service"
    
    print_step "Creating service file..."
    cat > /etc/systemd/system/etlegacy-bot.service <<EOF
[Unit]
Description=ET:Legacy Discord Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$DEPLOY_DIR
Environment="PATH=$DEPLOY_DIR/$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$DEPLOY_DIR/$VENV_DIR/bin/python3 $DEPLOY_DIR/bot/ultimate_bot.py
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
}

start_service() {
    if [ "$SKIP_SYSTEMD" = true ]; then
        return
    fi
    
    print_header "Starting Bot Service"
    
    if systemctl is-active --quiet etlegacy-bot 2>/dev/null; then
        print_warning "Service is already running"
        if prompt_yes_no "Restart service?"; then
            systemctl restart etlegacy-bot
            print_success "Service restarted"
        fi
    else
        systemctl start etlegacy-bot
        print_success "Service started"
    fi
    
    # Wait for service to start
    sleep 3
    
    # Check service status
    if systemctl is-active --quiet etlegacy-bot 2>/dev/null; then
        print_success "Bot is running!"
    else
        print_error "Bot failed to start - checking logs..."
        journalctl -u etlegacy-bot -n 20 --no-pager
    fi
}

show_completion_summary() {
    print_header "Installation Complete! 🎉"
    
    if [ "$MODE" = "env-only" ]; then
        echo -e "${GREEN}${BOLD}✓ Python environment setup complete!${NC}"
        echo ""
        echo -e "${BOLD}To activate the virtual environment:${NC}"
        echo "  source $VENV_DIR/bin/activate"
        echo ""
        echo -e "${BOLD}To run the bot:${NC}"
        echo "  python3 bot/ultimate_bot.py"
        echo ""
        return
    fi
    
    if [ "$SKIP_SYSTEMD" = false ]; then
        echo -e "${BOLD}Service Status:${NC}"
        systemctl status etlegacy-bot --no-pager -l | head -20 || true
        echo ""
    fi
    
    echo -e "${BOLD}Useful Commands:${NC}"
    if [ "$SKIP_SYSTEMD" = false ]; then
        echo "  View logs:      sudo journalctl -u etlegacy-bot -f"
        echo "  Restart bot:    sudo systemctl restart etlegacy-bot"
        echo "  Stop bot:       sudo systemctl stop etlegacy-bot"
        echo "  Service status: sudo systemctl status etlegacy-bot"
    else
        echo "  Start bot:      cd $DEPLOY_DIR && $VENV_DIR/bin/python3 bot/ultimate_bot.py"
        echo "  Activate venv:  source $DEPLOY_DIR/$VENV_DIR/bin/activate"
    fi
    echo ""
    
    if [ "$SKIP_POSTGRESQL" = false ]; then
        echo -e "${BOLD}Database Access:${NC}"
        echo "  psql -U $PG_USER -d $PG_DATABASE"
        echo ""
    fi
    
    echo -e "${BOLD}Configuration Files:${NC}"
    echo "  Bot config:     $DEPLOY_DIR/.env"
    if [ "$SKIP_SYSTEMD" = false ]; then
        echo "  Service file:   /etc/systemd/system/etlegacy-bot.service"
    fi
    echo ""
    
    if [ "$SKIP_GIT_CLONE" = false ]; then
        echo -e "${BOLD}Update Bot:${NC}"
        echo "  cd $DEPLOY_DIR"
        echo "  git pull origin $REPO_BRANCH"
        if [ "$SKIP_SYSTEMD" = false ]; then
            echo "  sudo systemctl restart etlegacy-bot"
        fi
        echo ""
    fi
    
    if [ "$SKIP_POSTGRESQL" = false ]; then
        echo -e "${BOLD}Re-import Stats:${NC}"
        echo "  cd $DEPLOY_DIR"
        echo "  $VENV_DIR/bin/python3 postgresql_database_manager.py"
        if [ "$SKIP_SYSTEMD" = false ]; then
            echo "  sudo systemctl restart etlegacy-bot"
        fi
        echo ""
    fi
    
    if [ ! -z "$PG_PASSWORD" ]; then
        echo -e "${BOLD}Database Password:${NC}"
        echo "  $PG_PASSWORD"
        echo "  ${YELLOW}(Saved to $DEPLOY_DIR/.env)${NC}"
        echo ""
    fi
    
    echo -e "${GREEN}${BOLD}✓ Installation successful!${NC}"
    if [ "$SKIP_SYSTEMD" = false ]; then
        echo -e "${BOLD}Test the bot in Discord with commands like: !last_session, !stats, !leaderboard${NC}"
    fi
    echo ""
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    parse_arguments "$@"
    
    # Show banner
    print_header "ET:Legacy Discord Bot - Installation v${VERSION}"
    
    echo -e "${BOLD}Installation Mode: ${GREEN}$MODE${NC}"
    echo ""
    echo -e "${BOLD}This script will:${NC}"
    
    if [ "$SKIP_POSTGRESQL" = false ]; then
        echo "  • Install and configure PostgreSQL"
    fi
    echo "  • Install Python 3 and dependencies"
    echo "  • Setup virtual environment"
    if [ "$SKIP_GIT_CLONE" = false ]; then
        echo "  • Clone repository to $DEPLOY_DIR"
    fi
    if [ "$SKIP_POSTGRESQL" = false ]; then
        echo "  • Configure database and .env file"
    fi
    if [ "$SKIP_DB_IMPORT" = false ] && [ "$SKIP_POSTGRESQL" = false ]; then
        echo "  • Initialize database schema"
    fi
    if [ "$SKIP_SYSTEMD" = false ]; then
        echo "  • Create and start systemd service"
    fi
    echo ""
    
    if ! prompt_yes_no "Continue with installation?"; then
        echo "Installation cancelled."
        exit 0
    fi
    
    # Run installation steps
    check_prerequisites
    update_system
    
    if [ "$SKIP_POSTGRESQL" = false ]; then
        install_postgresql
    fi
    
    install_python
    
    if [ "$SKIP_POSTGRESQL" = false ]; then
        setup_database
    fi
    
    if [ "$SKIP_GIT_CLONE" = false ]; then
        clone_repository
    fi
    
    setup_python_venv
    configure_bot
    
    if [ "$SKIP_DB_IMPORT" = false ] && [ "$SKIP_POSTGRESQL" = false ]; then
        import_database
    fi
    
    if [ "$SKIP_SYSTEMD" = false ]; then
        create_systemd_service
        start_service
    fi
    
    show_completion_summary
}

################################################################################
# Script Entry Point
################################################################################

main "$@"
