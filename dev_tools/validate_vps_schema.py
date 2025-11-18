#!/usr/bin/env python3
"""
Validate VPS PostgreSQL schema matches expected structure
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

# Expected schema for player_aliases table
EXPECTED_SCHEMA = {
    'player_aliases': {
        'id': {'type': 'integer', 'nullable': False},
        'guid': {'type': 'text', 'nullable': False},
        'alias': {'type': 'text', 'nullable': False},
        'first_seen': {'type': 'timestamp without time zone', 'nullable': True},
        'last_seen': {'type': 'timestamp without time zone', 'nullable': True},
        'times_seen': {'type': 'integer', 'nullable': True}
    }
}

async def validate_schema():
    """Validate database schema against expected structure"""
    
    # Get database connection info
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost').split(':')[0],
        'port': int(os.getenv('POSTGRES_HOST', 'localhost:5432').split(':')[1]) if ':' in os.getenv('POSTGRES_HOST', 'localhost:5432') else 5432,
        'database': os.getenv('POSTGRES_DATABASE', 'etlegacy'),
        'user': os.getenv('POSTGRES_USER', 'etlegacy_user'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }
    
    print(f"🔍 Validating PostgreSQL schema: {db_config['database']}")
    print("=" * 70)
    
    conn = await asyncpg.connect(**db_config)
    
    try:
        # Get all tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        print(f"\n📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"  ✓ {table['table_name']}")
        
        # Validate player_aliases table specifically
        print("\n" + "=" * 70)
        print("🔍 Validating player_aliases table schema:")
        print("=" * 70)
        
        columns = await conn.fetch("""
            SELECT 
                column_name, 
                data_type, 
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_name = 'player_aliases' 
            ORDER BY ordinal_position
        """)
        
        if not columns:
            print("❌ ERROR: player_aliases table not found!")
            return False
        
        print(f"\n📋 Current schema ({len(columns)} columns):")
        all_valid = True
        
        for col in columns:
            col_name = col['column_name']
            data_type = col['data_type']
            nullable = col['is_nullable'] == 'YES'
            default = col['column_default'] if col['column_default'] else 'NULL'
            
            # Check if expected
            if col_name in EXPECTED_SCHEMA['player_aliases']:
                expected = EXPECTED_SCHEMA['player_aliases'][col_name]
                type_match = data_type == expected['type']
                status = "✅" if type_match else "⚠️"
                
                print(f"  {status} {col_name}: {data_type} (nullable: {nullable}, default: {default})")
                
                if not type_match:
                    print(f"      Expected: {expected['type']}")
                    all_valid = False
            else:
                print(f"  ℹ️  {col_name}: {data_type} (not in expected schema)")
        
        # Check for missing columns
        print("\n🔍 Checking for missing columns:")
        found_columns = {col['column_name'] for col in columns}
        missing = set(EXPECTED_SCHEMA['player_aliases'].keys()) - found_columns
        
        if missing:
            print(f"  ❌ Missing columns: {', '.join(missing)}")
            all_valid = False
        else:
            print("  ✅ All expected columns present")
        
        # Check indexes
        print("\n" + "=" * 70)
        print("🔍 Checking indexes on player_aliases:")
        print("=" * 70)
        
        indexes = await conn.fetch("""
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename = 'player_aliases'
            ORDER BY indexname
        """)
        
        if indexes:
            print(f"\n📋 Found {len(indexes)} indexes:")
            for idx in indexes:
                print(f"  ✓ {idx['indexname']}")
                print(f"    {idx['indexdef']}")
        else:
            print("  ⚠️  No indexes found (consider adding UNIQUE constraint on guid+alias)")
        
        # Check constraints
        print("\n" + "=" * 70)
        print("🔍 Checking constraints on player_aliases:")
        print("=" * 70)
        
        constraints = await conn.fetch("""
            SELECT 
                conname as constraint_name,
                contype as constraint_type
            FROM pg_constraint
            WHERE conrelid = 'player_aliases'::regclass
            ORDER BY conname
        """)
        
        if constraints:
            print(f"\n📋 Found {len(constraints)} constraints:")
            constraint_types = {
                'p': 'PRIMARY KEY',
                'u': 'UNIQUE',
                'f': 'FOREIGN KEY',
                'c': 'CHECK'
            }
            for con in constraints:
                con_type = constraint_types.get(con['constraint_type'], con['constraint_type'])
                print(f"  ✓ {con['constraint_name']} ({con_type})")
        else:
            print("  ℹ️  No constraints found")
        
        # Test data count
        print("\n" + "=" * 70)
        print("📊 Data Statistics:")
        print("=" * 70)
        
        row_count = await conn.fetchval("SELECT COUNT(*) FROM player_aliases")
        print(f"\n  Total rows: {row_count:,}")
        
        if row_count > 0:
            # Show sample data
            sample = await conn.fetch("""
                SELECT guid, alias, first_seen, last_seen, times_seen
                FROM player_aliases
                ORDER BY last_seen DESC
                LIMIT 5
            """)
            
            print("\n  📝 Recent aliases:")
            for row in sample:
                ts = row['times_seen'] if row['times_seen'] else 0
                print(f"    • {row['alias'][:20]:20} (GUID: {row['guid'][:8]}...) - seen {ts} times")
        
        # Final verdict
        print("\n" + "=" * 70)
        if all_valid:
            print("✅ VALIDATION PASSED - Schema is correct!")
        else:
            print("⚠️  VALIDATION WARNINGS - Some schema mismatches detected")
        print("=" * 70)
        
        return all_valid
        
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(validate_schema())
