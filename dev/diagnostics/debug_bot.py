#!/usr/bin/env python3
"""
Test script to diagnose the bot command registration issue
"""
import sys
import os
sys.path.append('.')

try:
    from bot.ultimate_bot import UltimateETLegacyBot
    print("✅ Bot import successful")
    
    # Try to create bot instance
    bot = UltimateETLegacyBot()
    print("✅ Bot instance created")
    
    # Check commands
    commands = list(bot.commands)
    print(f"📋 Registered commands: {len(commands)}")
    for cmd in commands:
        print(f"  - {cmd.name}")
    
    # Check if specific methods exist
    methods_to_check = ['ping', 'help_command', 'stats_command', 'session_start']
    for method_name in methods_to_check:
        if hasattr(bot, method_name):
            method = getattr(bot, method_name)
            print(f"✅ Method {method_name} exists: {type(method)}")
            # Check if it has command decorator
            if hasattr(method, 'callback'):
                print(f"  - Has callback (likely a command)")
            else:
                print(f"  - No callback (not a registered command)")
        else:
            print(f"❌ Method {method_name} missing")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()