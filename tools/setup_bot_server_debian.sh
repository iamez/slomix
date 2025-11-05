#!/bin/bash
# Bot Server Setup Script (Debian/Ubuntu)
# Run this on the VPS that will host the Discord bot

set -e  # Exit on error

echo "============================================"
echo "  Discord Bot Server Setup"
echo "  For: Debian/Ubuntu"
echo "============================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Please run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${BLUE}Step 1: Updating system...${NC}"
apt update
apt upgrade -y

echo ""
echo -e "${BLUE}Step 2: Installing dependencies...${NC}"
apt install -y python3 python3-pip python3-venv git postgresql-client

echo ""
echo -e "${BLUE}Step 3: Installing Python packages...${NC}"
pip3 install --upgrade pip

echo ""
echo -e "${BLUE}Step 4: Creating bot user...${NC}"
if ! id "etlegacy" &>/dev/null; then
    useradd -m -s /bin/bash etlegacy
    echo -e "${GREEN}✅ User 'etlegacy' created${NC}"
else
    echo -e "${YELLOW}⚠️  User 'etlegacy' already exists${NC}"
fi

echo ""
echo -e "${BLUE}Step 5: Setting up bot directory...${NC}"
BOT_DIR="/home/etlegacy/bot"
if [ ! -d "$BOT_DIR" ]; then
    mkdir -p $BOT_DIR
    chown -R etlegacy:etlegacy $BOT_DIR
    echo -e "${GREEN}✅ Bot directory created at $BOT_DIR${NC}"
else
    echo -e "${YELLOW}⚠️  Bot directory already exists${NC}"
fi

echo ""
echo -e "${YELLOW}📝 Manual Steps Required:${NC}"
echo ""
echo "1. Clone your repository:"
echo "   sudo -u etlegacy git clone https://github.com/iamez/slomix.git $BOT_DIR"
echo ""
echo "2. Switch to migration branch:"
echo "   cd $BOT_DIR && sudo -u etlegacy git checkout vps-network-migration"
echo ""
echo "3. Create virtual environment:"
echo "   sudo -u etlegacy python3 -m venv $BOT_DIR/.venv"
echo ""
echo "4. Install requirements:"
echo "   sudo -u etlegacy $BOT_DIR/.venv/bin/pip install -r $BOT_DIR/requirements.txt"
echo ""
echo "5. Create config.json:"
cat << 'EOF'
   {
     "token": "YOUR_DISCORD_BOT_TOKEN",
     "database_type": "postgresql",
     "postgresql_host": "DB_SERVER_IP",
     "postgresql_port": 5432,
     "postgresql_database": "etlegacy",
     "postgresql_user": "etlegacy_user",
     "postgresql_password": "PASSWORD_FROM_DB_SERVER",
     "stats_channel_id": "YOUR_CHANNEL_ID",
     "admin_channel_id": "YOUR_CHANNEL_ID"
   }
EOF
echo ""
echo "6. Test database connection:"
echo "   psql -h DB_SERVER_IP -U etlegacy_user -d etlegacy"
echo ""
echo "7. Run migration (if needed):"
echo "   sudo -u etlegacy $BOT_DIR/.venv/bin/python $BOT_DIR/tools/migrate_to_postgresql.py"
echo ""

echo ""
echo -e "${BLUE}Step 6: Creating systemd service...${NC}"

cat > /etc/systemd/system/etlegacy-bot.service << 'EOF'
[Unit]
Description=ET:Legacy Discord Bot
After=network.target

[Service]
Type=simple
User=etlegacy
Group=etlegacy
WorkingDirectory=/home/etlegacy/bot
Environment="PATH=/home/etlegacy/bot/.venv/bin"
ExecStart=/home/etlegacy/bot/.venv/bin/python bot/ultimate_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/etlegacy/bot/logs/bot.log
StandardError=append:/home/etlegacy/bot/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo -e "${GREEN}✅ Systemd service created${NC}"

echo ""
echo "============================================"
echo -e "${GREEN}✅ Bot Server Setup Complete!${NC}"
echo "============================================"
echo ""
echo -e "${BLUE}To start the bot:${NC}"
echo "  sudo systemctl start etlegacy-bot"
echo "  sudo systemctl enable etlegacy-bot  # Auto-start on boot"
echo ""
echo -e "${BLUE}To check bot status:${NC}"
echo "  sudo systemctl status etlegacy-bot"
echo ""
echo -e "${BLUE}To view logs:${NC}"
echo "  sudo journalctl -u etlegacy-bot -f"
echo "  tail -f /home/etlegacy/bot/logs/bot.log"
echo ""
