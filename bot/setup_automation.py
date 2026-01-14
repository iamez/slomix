"""
🚀 Quick Setup Script for Automation
====================================

This script automates the setup process for production automation.
It will:
1. Install required dependencies
2. Check/create .env configuration
3. Verify bot file exists
4. Show integration status

Run this FIRST before integrating automation features.
"""

import subprocess
import sys
import os
import shutil
from datetime import datetime


def print_header(text):
    """Print a nice header"""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def print_step(number, text):
    """Print a step"""
    print(f"\n{'=' * 70}")
    print(f"Step {number}: {text}")
    print("=" * 70)


def install_dependencies():
    """Install required Python packages"""
    print_step(1, "Installing Dependencies")
    
    packages = ["psutil"]
    
    for package in packages:
        print(f"\n📦 Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    return True


def check_bot_file():
    """Check if bot file exists"""
    print_step(2, "Checking Bot File")
    
    bot_file = "ultimate_bot.py"
    
    if os.path.exists(bot_file):
        print(f"✅ Found: {bot_file}")
        
        # Get file info
        size_kb = os.path.getsize(bot_file) / 1024
        modified = datetime.fromtimestamp(os.path.getmtime(bot_file))
        
        print(f"   Size: {size_kb:.1f} KB")
        print(f"   Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Create backup
        response = input("\n💾 Create backup before modifications? (yes/no): ").strip().lower()
        if response == "yes":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{bot_file}.backup_before_automation_{timestamp}"
            shutil.copy2(bot_file, backup_file)
            print(f"✅ Backup created: {backup_file}")
        
        return True
    else:
        print(f"❌ Bot file not found: {bot_file}")
        print("   Make sure you're in the bot/ directory")
        return False


def check_env_file():
    """Check and setup .env file"""
    print_step(3, "Checking .env Configuration")
    
    env_file = "../.env"
    env_example = "../.env.example"
    
    if os.path.exists(env_file):
        print(f"✅ Found: {env_file}")
        
        # Read current .env
        with open(env_file, "r") as f:
            content = f.read()
        
        # Check if ADMIN_CHANNEL_ID exists
        if "ADMIN_CHANNEL_ID" not in content:
            print("\n⚠️  ADMIN_CHANNEL_ID not found in .env")
            
            response = input("Add ADMIN_CHANNEL_ID to .env? (yes/no): ").strip().lower()
            if response == "yes":
                channel_id = input("Enter admin channel ID (or press Enter to use STATS_CHANNEL_ID): ").strip()
                
                # Add to .env
                with open(env_file, "a") as f:
                    f.write("\n\n# ==================\n")
                    f.write("# AUTOMATION ENHANCEMENTS\n")
                    f.write("# ==================\n")
                    if channel_id:
                        f.write(f"ADMIN_CHANNEL_ID={channel_id}\n")
                    else:
                        f.write("# ADMIN_CHANNEL_ID=  # Leave empty to use STATS_CHANNEL_ID\n")
                
                print("✅ .env updated")
        else:
            print("✅ ADMIN_CHANNEL_ID found in .env")
        
        return True
    else:
        print(f"⚠️  .env file not found at: {env_file}")
        
        if os.path.exists(env_example):
            response = input(f"Create .env from {env_example}? (yes/no): ").strip().lower()
            if response == "yes":
                shutil.copy2(env_example, env_file)
                print(f"✅ Created: {env_file}")
                print("⚠️  Remember to configure it with your values!")
                return True
        
        print("❌ Cannot proceed without .env file")
        return False


def check_database():
    """Check database exists"""
    print_step(4, "Checking Database")
    
    db_file = "etlegacy_production.db"
    
    if os.path.exists(db_file):
        print(f"✅ Found: {db_file}")
        
        size_mb = os.path.getsize(db_file) / (1024 * 1024)
        print(f"   Size: {size_mb:.2f} MB")
        
        # Create backups directory
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            print(f"✅ Created backup directory: {backup_dir}/")
        else:
            print(f"✅ Backup directory exists: {backup_dir}/")
        
        return True
    else:
        print(f"⚠️  Database not found: {db_file}")
        print("   Bot will create it on first run")
        return True  # Not critical


def show_integration_instructions():
    """Show next steps"""
    print_header("📚 Next Steps - Integration")
    
    print("\n✅ Setup Complete! Now you need to integrate the features.\n")
    
    print("🔧 Integration Options:\n")
    
    print("Option 1: Run the Integration Helper (RECOMMENDED)")
    print("   python integrate_automation.py")
    print("   → Provides step-by-step guidance\n")
    
    print("Option 2: Manual Integration")
    print("   1. Open: automation_enhancements.py")
    print("   2. Copy methods to ultimate_bot.py")
    print("   3. Follow instructions at bottom of file\n")
    
    print("Option 3: Read the Guide")
    print("   See: ../PRODUCTION_AUTOMATION_GUIDE.md")
    print("   → Complete documentation\n")
    
    print("🧪 After Integration - Test:")
    print("   python test_automation.py")
    print("   → Validates everything works\n")
    
    print("🚀 Then Run Your Bot:")
    print("   python ultimate_bot.py")
    print("   → Start monitoring!\n")
    
    print("=" * 70)


def main():
    """Main setup function"""
    print_header("🤖 ET:Legacy Bot - Automation Setup")
    print("\nThis script will prepare your bot for production automation.\n")
    
    # Change to bot directory if not there
    if not os.path.exists("ultimate_bot.py"):
        if os.path.exists("bot/ultimate_bot.py"):
            print("📁 Changing to bot/ directory...")
            os.chdir("bot")
        else:
            print("❌ Cannot find bot directory!")
            print("   Run this script from project root or bot/ directory")
            return False
    
    # Run setup steps
    success = True
    
    # Step 1: Install dependencies
    if not install_dependencies():
        print("\n⚠️  Failed to install dependencies")
        print("   Try manually: pip install psutil")
        success = False
    
    # Step 2: Check bot file
    if not check_bot_file():
        success = False
    
    # Step 3: Check .env
    if not check_env_file():
        success = False
    
    # Step 4: Check database
    check_database()  # Not critical
    
    # Show results
    print_header("🎯 Setup Summary")
    
    if success:
        print("\n✅ All checks passed!")
        print("✅ Dependencies installed")
        print("✅ Bot file found")
        print("✅ Configuration ready")
        
        show_integration_instructions()
        
        return True
    else:
        print("\n⚠️  Some checks failed")
        print("   Fix the issues above and run setup again")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup error: {e}")
        sys.exit(1)
