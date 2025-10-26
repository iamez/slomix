#!/usr/bin/env python3
"""
Bot startup test without Discord connection
"""
import os
import sys
import asyncio

# Add the current directory to the path to import bot modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_bot_import():
    """Test if we can import and initialize the bot class"""
    try:
        print("🔍 Testing bot import...")
        
        # Set a dummy token to avoid Discord connection
        os.environ['DISCORD_BOT_TOKEN'] = 'dummy_token_for_testing'
        
        # Import the bot
        from bot.ultimate_bot import UltimateETLegacyBot
        print("✅ Bot class imported successfully!")
        
        # Try to create bot instance (but don't run it)
        print("🔍 Testing bot initialization...")
        bot = UltimateETLegacyBot()
        print("✅ Bot instance created successfully!")
        
        # Check if database path is correct
        print(f"📂 Database path: {bot.db_path}")
        
        # Test database initialization without running the bot
        print("🔍 Testing database initialization...")
        await bot.initialize_database()
        print("✅ Database initialization successful!")
        
        print("\n🎯 Bot structure test completed successfully!")
        
    except Exception as e:
        print(f"❌ Bot test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bot_import())