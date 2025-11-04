#!/usr/bin/env python3
"""
Quick test to verify network database access works
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

db_path = os.getenv('DATABASE_PATH', 'bot/etlegacy_production.db')

print(f"Testing database connection...")
print(f"Database path: {db_path}")
print(f"Path exists: {Path(db_path).exists()}")

try:
    # Test connection
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    # Test query
    cursor.execute("SELECT COUNT(*) FROM rounds")
    count = cursor.fetchone()[0]
    
    print(f"✅ SUCCESS! Database accessible.")
    print(f"   Found {count} sessions in database")
    
    # Test write (important for network shares)
    cursor.execute("PRAGMA journal_mode=WAL")
    result = cursor.fetchone()[0]
    print(f"   Journal mode: {result}")
    
    conn.close()
    print("\n✅ Network database test PASSED!")
    
except Exception as e:
    print(f"\n❌ FAILED: {e}")
    print("\nTroubleshooting:")
    print("1. Check if Samba share is accessible")
    print("2. Verify path in .env is correct")
    print("3. Try UNC path instead of mapped drive")
    print("4. Check file permissions on Samba share")
