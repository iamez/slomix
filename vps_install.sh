#!/bin/bash
# ET:Legacy Discord Bot - VPS Installation Script
# Run this on your Linux VPS in /home/samba/share/slomix_discord/

set -e  # Exit on any error

echo "🚀 ET:Legacy Discord Bot - VPS Installation"
echo "=============================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "❌ Please don't run as root. Run as regular user with sudo access."
    exit 1
fi

# 1. Install system dependencies
echo ""
echo "📦 Step 1: Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib

# 2. Setup PostgreSQL
echo ""
echo "🗄️  Step 2: Setting up PostgreSQL database..."
sudo -u postgres psql <<EOF
-- Create database
CREATE DATABASE etlegacy;

-- Create user
CREATE USER etlegacy_user WITH PASSWORD '123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etlegacy_user;

-- Exit
\q
EOF

echo "✅ PostgreSQL database 'etlegacy' created"
echo "✅ User 'etlegacy_user' created (change password in .env file!)"

# 3. Create Python virtual environment
echo ""
echo "🐍 Step 3: Creating Python virtual environment..."
python3 -m venv venv
source venv/Scripts/activate

# 4. Install Python dependencies
echo ""
echo "📚 Step 4: Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create .env file from example
echo ""
echo "⚙️  Step 5: Creating .env configuration file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env file created - YOU MUST EDIT THIS FILE!"
else
    echo "⚠️  .env file already exists - skipping"
fi

# 6. Initialize database schema
echo ""
echo "🔧 Step 6: Creating database tables..."
python postgresql_database_manager.py <<EOF
1
y
EOF

echo ""
echo "=============================================="
echo "✅ Installation Complete!"
echo ""
echo "⚠️  IMPORTANT: Edit .env file with your settings:"
echo "   1. Set DISCORD_BOT_TOKEN=your_token_here"
echo "   2. Set POSTGRES_PASSWORD=change_this_password"
echo "   3. Set LOCAL_STATS_PATH=/path/to/stats/files"
echo ""
echo "To start the bot:"
echo "   ./start_bot.sh"
echo ""
echo "To test the bot:"
echo "   source venv/bin/activate"
echo "   python bot/ultimate_bot.py"
echo "=============================================="
