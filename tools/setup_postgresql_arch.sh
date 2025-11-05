#!/bin/bash
# PostgreSQL Setup for Arch Linux / EndeavourOS (Database Server)
# Run this on the VPS that will host the PostgreSQL database

set -e  # Exit on error

echo "============================================"
echo "  PostgreSQL Database Server Setup"
echo "  For: Arch Linux / EndeavourOS"
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
pacman -Syu --noconfirm

echo ""
echo -e "${BLUE}Step 2: Installing PostgreSQL...${NC}"
pacman -S --noconfirm postgresql

echo ""
echo -e "${BLUE}Step 3: Initializing PostgreSQL data directory...${NC}"
# Initialize database cluster if not already done
if [ ! -d "/var/lib/postgres/data" ]; then
    sudo -u postgres initdb -D /var/lib/postgres/data
    echo -e "${GREEN}✅ Database cluster initialized${NC}"
else
    echo -e "${YELLOW}⚠️  Database cluster already exists${NC}"
fi

echo ""
echo -e "${BLUE}Step 4: Starting PostgreSQL service...${NC}"
systemctl start postgresql
systemctl enable postgresql
systemctl status postgresql --no-pager

echo ""
echo -e "${BLUE}Step 5: Creating database and user...${NC}"

# Generate secure password
DB_PASSWORD=$(openssl rand -base64 32)

sudo -u postgres psql << EOF
CREATE DATABASE etlegacy;
CREATE USER etlegacy_user WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etlegacy_user;
\c etlegacy
GRANT ALL ON SCHEMA public TO etlegacy_user;
ALTER DATABASE etlegacy OWNER TO etlegacy_user;
EOF

echo -e "${GREEN}✅ Database 'etlegacy' created${NC}"
echo -e "${GREEN}✅ User 'etlegacy_user' created${NC}"

echo ""
echo -e "${BLUE}Step 6: Configuring PostgreSQL for remote connections...${NC}"

PG_CONF_DIR="/var/lib/postgres/data"

# Backup original configs
cp ${PG_CONF_DIR}/postgresql.conf ${PG_CONF_DIR}/postgresql.conf.backup
cp ${PG_CONF_DIR}/pg_hba.conf ${PG_CONF_DIR}/pg_hba.conf.backup

# Configure PostgreSQL to listen on all interfaces
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" ${PG_CONF_DIR}/postgresql.conf

# Allow remote connections (replace with your bot server IP for security)
echo "# Allow bot server connection" >> ${PG_CONF_DIR}/pg_hba.conf
echo "host    etlegacy    etlegacy_user    0.0.0.0/0    md5" >> ${PG_CONF_DIR}/pg_hba.conf

echo -e "${GREEN}✅ PostgreSQL configured for remote connections${NC}"
echo -e "${YELLOW}⚠️  For production, restrict to bot server IP only!${NC}"

echo ""
echo -e "${BLUE}Step 7: Configuring firewall...${NC}"

# Check if ufw is installed
if command -v ufw &> /dev/null; then
    ufw allow 5432/tcp
    echo -e "${GREEN}✅ Firewall rule added (ufw)${NC}"
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=5432/tcp
    firewall-cmd --reload
    echo -e "${GREEN}✅ Firewall rule added (firewalld)${NC}"
else
    echo -e "${YELLOW}⚠️  No firewall detected. Manually allow port 5432 if needed${NC}"
fi

echo ""
echo -e "${BLUE}Step 8: Restarting PostgreSQL...${NC}"
systemctl restart postgresql

echo ""
echo -e "${BLUE}Step 9: Testing connection...${NC}"
sudo -u postgres psql -d etlegacy -c "SELECT version();" > /dev/null
echo -e "${GREEN}✅ Database connection test passed${NC}"

echo ""
echo "============================================"
echo -e "${GREEN}✅ PostgreSQL Setup Complete!${NC}"
echo "============================================"
echo ""
echo -e "${YELLOW}📝 IMPORTANT - Save these credentials:${NC}"
echo ""
echo "  Database Host: $(hostname -I | awk '{print $1}')"
echo "  Database Port: 5432"
echo "  Database Name: etlegacy"
echo "  Database User: etlegacy_user"
echo "  Database Password: $DB_PASSWORD"
echo ""
echo -e "${YELLOW}⚠️  SECURITY RECOMMENDATIONS:${NC}"
echo "  1. Edit ${PG_CONF_DIR}/pg_hba.conf"
echo "     Replace '0.0.0.0/0' with your bot server IP"
echo "  2. Restart PostgreSQL: systemctl restart postgresql"
echo "  3. Enable SSL for production (optional but recommended)"
echo "  4. Setup regular backups with pg_dump"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Copy schema file to this server:"
echo "     scp tools/schema_postgresql.sql user@this-server:/tmp/"
echo "  2. Apply schema:"
echo "     sudo -u postgres psql -d etlegacy -f /tmp/schema_postgresql.sql"
echo "  3. Update bot server config.json with above credentials"
echo "  4. Run migration from bot server"
echo ""

# Save credentials to file
cat > /root/etlegacy_db_credentials.txt << EOF
PostgreSQL Database Credentials
================================
Host: $(hostname -I | awk '{print $1}')
Port: 5432
Database: etlegacy
User: etlegacy_user
Password: $DB_PASSWORD

Connection String:
postgresql://etlegacy_user:$DB_PASSWORD@$(hostname -I | awk '{print $1}'):5432/etlegacy

Generated: $(date)
EOF

echo -e "${GREEN}✅ Credentials saved to: /root/etlegacy_db_credentials.txt${NC}"
