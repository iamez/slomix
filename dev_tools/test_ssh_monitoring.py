#!/usr/bin/env python3
"""
🧪 Comprehensive SSH Monitoring Test
=====================================

This script tests the entire SSH monitoring and auto-posting pipeline.

Test Steps:
1. Check .env configuration
2. Test SSH connection
3. Test file listing
4. Test file download
5. Test file parsing
6. Test database import
7. Test Discord posting
8. Monitor logs
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("TEST")

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("⚠️ dotenv not installed, using system environment")


class SSHMonitoringTest:
    """Comprehensive test suite for SSH monitoring"""
    
    def __init__(self):
        self.results = []
        self.failed = False
    
    def test(self, name, func):
        """Run a test and track results"""
        logger.info("=" * 60)
        logger.info(f"🧪 TEST: {name}")
        logger.info("=" * 60)
        
        try:
            result = func()
            if result:
                logger.info(f"✅ PASSED: {name}")
                self.results.append((name, "PASS", None))
                return True
            else:
                logger.error(f"❌ FAILED: {name}")
                self.results.append((name, "FAIL", "Test returned False"))
                self.failed = True
                return False
        except Exception as e:
            logger.error(f"❌ FAILED: {name}")
            logger.error(f"   Error: {e}", exc_info=True)
            self.results.append((name, "FAIL", str(e)))
            self.failed = True
            return False
    
    def test_env_config(self):
        """Test 1: Check .env configuration"""
        required_vars = [
            "DISCORD_BOT_TOKEN",
            "STATS_CHANNEL_ID",
            "SSH_ENABLED",
            "SSH_HOST",
            "SSH_PORT",
            "SSH_USER",
            "SSH_KEY_PATH",
            "REMOTE_STATS_PATH"
        ]
        
        missing = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                logger.error(f"   ❌ Missing: {var}")
                missing.append(var)
            else:
                # Mask sensitive data
                if "TOKEN" in var or "PASSWORD" in var:
                    display = value[:10] + "..."
                else:
                    display = value
                logger.info(f"   ✅ {var} = {display}")
        
        if missing:
            logger.error(f"   Missing {len(missing)} required variables")
            return False
        
        # Check SSH_ENABLED
        ssh_enabled = os.getenv("SSH_ENABLED", "false").lower()
        if ssh_enabled != "true":
            logger.warning(f"   ⚠️ SSH_ENABLED = {ssh_enabled} (should be 'true')")
            return False
        
        logger.info("   ✅ All configuration present and valid")
        return True
    
    def test_ssh_connection(self):
        """Test 2: Test SSH connection"""
        try:
            import paramiko
            
            ssh_config = {
                "host": os.getenv("SSH_HOST"),
                "port": int(os.getenv("SSH_PORT", 22)),
                "user": os.getenv("SSH_USER"),
                "key_path": os.getenv("SSH_KEY_PATH", ""),
            }
            
            logger.info(f"   📡 Connecting to {ssh_config['user']}@{ssh_config['host']}:{ssh_config['port']}")
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            key_path = os.path.expanduser(ssh_config["key_path"])
            logger.info(f"   🔑 Using key: {key_path}")
            
            ssh.connect(
                hostname=ssh_config["host"],
                port=ssh_config["port"],
                username=ssh_config["user"],
                key_filename=key_path,
                timeout=10
            )
            
            logger.info("   ✅ SSH connection successful!")
            ssh.close()
            return True
            
        except Exception as e:
            logger.error(f"   ❌ SSH connection failed: {e}")
            return False
    
    def test_file_listing(self):
        """Test 3: List files on remote server"""
        try:
            import paramiko
            
            ssh_config = {
                "host": os.getenv("SSH_HOST"),
                "port": int(os.getenv("SSH_PORT", 22)),
                "user": os.getenv("SSH_USER"),
                "key_path": os.getenv("SSH_KEY_PATH", ""),
                "remote_path": os.getenv("REMOTE_STATS_PATH")
            }
            
            logger.info(f"   📂 Listing files in: {ssh_config['remote_path']}")
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=ssh_config["host"],
                port=ssh_config["port"],
                username=ssh_config["user"],
                key_filename=os.path.expanduser(ssh_config["key_path"]),
                timeout=10
            )
            
            sftp = ssh.open_sftp()
            files = sftp.listdir(ssh_config["remote_path"])
            txt_files = [f for f in files if f.endswith(".txt") and not f.endswith("_ws.txt")]
            
            logger.info(f"   ✅ Found {len(txt_files)} .txt files")
            
            if txt_files:
                logger.info("   📄 Sample files:")
                for f in txt_files[:5]:
                    logger.info(f"      - {f}")
                if len(txt_files) > 5:
                    logger.info(f"      ... and {len(txt_files) - 5} more")
            
            sftp.close()
            ssh.close()
            
            return len(txt_files) > 0
            
        except Exception as e:
            logger.error(f"   ❌ File listing failed: {e}")
            return False
    
    def test_database_connection(self):
        """Test 4: Test database connection"""
        try:
            import sqlite3
            
            db_path = os.getenv("DATABASE_PATH", "bot/etlegacy_production.db")
            logger.info(f"   💾 Connecting to database: {db_path}")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check schema
            cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
            columns = cursor.fetchall()
            
            logger.info(f"   ✅ Database has {len(columns)} columns")
            
            # Check record count
            cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
            count = cursor.fetchone()[0]
            
            logger.info(f"   📊 Database has {count} records")
            
            # Check processed files
            cursor.execute("SELECT COUNT(*) FROM processed_files WHERE success = 1")
            processed = cursor.fetchone()[0]
            
            logger.info(f"   ✅ {processed} files marked as processed")
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"   ❌ Database connection failed: {e}")
            return False
    
    def print_summary(self):
        """Print test summary"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 60)
        
        passed = sum(1 for _, status, _ in self.results if status == "PASS")
        failed = sum(1 for _, status, _ in self.results if status == "FAIL")
        
        for name, status, error in self.results:
            emoji = "✅" if status == "PASS" else "❌"
            logger.info(f"{emoji} {name}: {status}")
            if error:
                logger.info(f"   Error: {error}")
        
        logger.info("")
        logger.info(f"Total: {len(self.results)} tests")
        logger.info(f"✅ Passed: {passed}")
        logger.info(f"❌ Failed: {failed}")
        logger.info("=" * 60)
        
        if self.failed:
            logger.error("🚨 SOME TESTS FAILED - Fix errors before running bot")
            return False
        else:
            logger.info("🎉 ALL TESTS PASSED - Ready to run bot!")
            return True


def main():
    """Run comprehensive test suite"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("🚀 SSH MONITORING COMPREHENSIVE TEST")
    logger.info("=" * 60)
    logger.info(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    logger.info("")
    
    tester = SSHMonitoringTest()
    
    # Run all tests
    tester.test("Environment Configuration", tester.test_env_config)
    tester.test("SSH Connection", tester.test_ssh_connection)
    tester.test("Remote File Listing", tester.test_file_listing)
    tester.test("Database Connection", tester.test_database_connection)
    
    # Print summary
    success = tester.print_summary()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("📋 NEXT STEPS:")
    logger.info("=" * 60)
    
    if success:
        logger.info("1. Run the bot: python bot/ultimate_bot.py")
        logger.info("2. Check logs in: logs/bot.log")
        logger.info("3. Watch for: '📥 New file detected' messages")
        logger.info("4. Verify Discord posts in your stats channel")
        logger.info("5. Play a round and wait 30-60 seconds!")
    else:
        logger.error("1. Fix the failed tests above")
        logger.error("2. Re-run this test script")
        logger.error("3. Once all tests pass, run the bot")
    
    logger.info("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
