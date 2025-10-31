#!/usr/bin/env python3
"""
Install SSH dependencies for production bot
"""

import subprocess
import sys

def install_ssh_dependencies():
    """Install required SSH libraries for file monitoring"""
    
    print("🔧 Installing SSH dependencies for production bot...")
    
    dependencies = [
        'paramiko',     # SSH client library
        'asyncssh',     # Async SSH library
        'cryptography'  # Cryptographic functions
    ]
    
    for package in dependencies:
        try:
            print(f"📦 Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    print("\n🎉 All SSH dependencies installed!")
    print("\n📝 Next steps:")
    print("1. Copy dev/.env.production to .env and configure your settings")
    print("2. Set up SSH key authentication to your game server")
    print("3. Test SSH connection: ssh et@puran")
    print("4. Run the production bot: python dev/production_comprehensive_bot.py")
    
    return True

if __name__ == "__main__":
    install_ssh_dependencies()