#!/bin/bash
# ET:Legacy Discord Bot - Startup Script
# Quick start script for running the bot

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "🔧 Activating virtual environment..."
    source venv/bin/activate
fi

# Start the bot
echo "🤖 Starting ET:Legacy Discord Bot..."
python3 bot/ultimate_bot.py
