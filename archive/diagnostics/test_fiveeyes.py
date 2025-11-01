"""
Quick test script to verify FIVEEYES cog loads and works
Run this before starting the full bot
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath('.'))

from analytics.config import config
from analytics.synergy_detector import SynergyDetector


async def test_config():
    """Test configuration system"""
    print("\n🧪 Testing Configuration System")
    print("=" * 50)
    
    # Check default state
    print(f"Analytics enabled: {config.is_enabled()}")
    print(f"Min games threshold: {config.get('synergy_analytics.min_games_threshold')}")
    print(f"Synergy command enabled: {config.is_command_enabled('synergy')}")
    print(f"Best duos command enabled: {config.is_command_enabled('best_duos')}")
    
    if config.is_enabled():
        print("\n⚠️  WARNING: Analytics is ENABLED")
        print("For safety, it should be disabled by default")
    else:
        print("\n✅ Analytics is disabled by default (safe!)")


async def test_synergy_detector():
    """Test synergy detector"""
    print("\n🧪 Testing Synergy Detector")
    print("=" * 50)
    
    detector = SynergyDetector()
    
    # Get best duos
    print("\nFetching top 3 duos from database...")
    duos = await detector.get_best_duos(limit=3)
    
    if duos:
        print(f"✅ Found {len(duos)} synergies")
        print("\nTop 3:")
        for idx, duo in enumerate(duos, 1):
            print(f"{idx}. {duo.player_a_name} + {duo.player_b_name}")
            print(f"   Synergy: {duo.synergy_score:.3f} | Games: {duo.games_same_team}")
    else:
        print("❌ No synergies found - run calculate_all first")


async def test_cog_import():
    """Test cog can be imported"""
    print("\n🧪 Testing Cog Import")
    print("=" * 50)
    
    try:
        from bot.cogs.synergy_analytics import SynergyAnalytics
        print("✅ SynergyAnalytics cog imports successfully")
        
        # Check methods exist
        methods = ['synergy_command', 'best_duos_command', 'team_builder_command']
        for method in methods:
            if hasattr(SynergyAnalytics, method):
                print(f"   ✅ {method} exists")
            else:
                print(f"   ❌ {method} missing")
        
    except Exception as e:
        print(f"❌ Error importing cog: {e}")


async def main():
    """Run all tests"""
    print("\n" + "=" * 50)
    print("🎯 FIVEEYES Pre-Flight Checks")
    print("=" * 50)
    
    await test_config()
    await test_synergy_detector()
    await test_cog_import()
    
    print("\n" + "=" * 50)
    print("✅ All pre-flight checks complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Start your bot normally")
    print("2. In Discord: !fiveeyes_enable")
    print("3. Test: !synergy @Player1 @Player2")
    print("4. Test: !best_duos")
    print("\n")


if __name__ == '__main__':
    asyncio.run(main())
