#!/bin/bash
################################################################################
# ET:Legacy Discord Bot - Quick Update Script
# Updates bot code and restarts service
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

DEPLOY_DIR="/slomix"
REPO_BRANCH="vps-network-migration"

echo -e "\n${BOLD}Updating ET:Legacy Discord Bot...${NC}\n"

# Check if directory exists
if [ ! -d "$DEPLOY_DIR" ]; then
    echo "Error: $DEPLOY_DIR not found. Run setup_linux_bot.sh first."
    exit 1
fi

cd $DEPLOY_DIR

# Pull latest changes
echo -e "${BLUE}▶${NC} Pulling latest changes from GitHub..."
git fetch origin
git checkout $REPO_BRANCH
git pull origin $REPO_BRANCH

# Restart service
echo -e "${BLUE}▶${NC} Restarting bot service..."
sudo systemctl restart etlegacy-bot

# Wait and check status
sleep 2

if systemctl is-active --quiet etlegacy-bot; then
    echo -e "\n${GREEN}✓ Bot updated and restarted successfully!${NC}\n"
    sudo systemctl status etlegacy-bot --no-pager -l | head -15
else
    echo -e "\n${RED}✗ Bot failed to restart. Check logs:${NC}"
    echo "  sudo journalctl -u etlegacy-bot -n 50"
fi

echo ""
