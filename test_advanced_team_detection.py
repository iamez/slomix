"""
Test and demonstrate the new Advanced Team Detection System

This script:
1. Tests the new detection system on a specific session
2. Shows confidence scores and quality metrics
3. Compares with old detection method (if available)
4. Validates the results
"""

import sys
import sqlite3
from bot.core.team_detector_integration import TeamDetectorIntegration


def test_detection(session_date: str, db_path: str = "bot/etlegacy_production.db"):
    """Test team detection for a session"""
    
    print("=" * 80)
    print("🎯 ADVANCED TEAM DETECTION TEST")
    print("=" * 80)
    print(f"Session Date: {session_date}")
    print(f"Database: {db_path}")
    print()
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False
    
    # Initialize detector
    detector = TeamDetectorIntegration(db_path)
    
    # Step 1: Check if teams already stored
    print("📋 Step 1: Checking for stored teams...")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT team_name, player_guids, player_names
        FROM session_teams
        WHERE session_start_date LIKE ? AND map_name = 'ALL'
        """,
        (f"{session_date}%",)
    )
    
    existing_teams = cursor.fetchall()
    if existing_teams:
        print(f"✅ Found {len(existing_teams)} stored teams")
        for team_name, guids, names in existing_teams:
            import json
            names_list = json.loads(names)
            print(f"   {team_name}: {len(names_list)} players - {', '.join(names_list[:5])}")
            if len(names_list) > 5:
                print(f"             ...and {len(names_list) - 5} more")
    else:
        print("⚠️  No stored teams found")
    print()
    
    # Step 2: Run detection
    print("🔍 Step 2: Running advanced detection...")
    result, is_reliable = detector.detect_and_validate(
        conn,
        session_date,
        require_high_confidence=False
    )
    
    if not result:
        print("❌ Detection failed!")
        conn.close()
        return False
    
    print("✅ Detection successful!")
    print()
    
    # Step 3: Show results
    print("📊 Step 3: Detection Results")
    print("-" * 80)
    
    metadata = result.get('metadata', {})
    
    print(f"Quality:      {metadata.get('detection_quality', 'unknown').upper()}")
    print(f"Confidence:   {metadata.get('avg_confidence', 0):.1%}")
    print(f"Strategy:     {metadata.get('strategy_used', 'unknown')}")
    print(f"Reliable:     {'✅ Yes' if is_reliable else '⚠️  No'}")
    print()
    
    # Team A
    team_a = result['Team A']
    print(f"🔴 Team A ({len(team_a['guids'])} players):")
    for i, name in enumerate(team_a['names'], 1):
        print(f"   {i:2d}. {name}")
    print()
    
    # Team B
    team_b = result['Team B']
    print(f"🔵 Team B ({len(team_b['guids'])} players):")
    for i, name in enumerate(team_b['names'], 1):
        print(f"   {i:2d}. {name}")
    print()
    
    # Warnings
    if metadata.get('uncertain_players'):
        print("⚠️  Uncertain Players:")
        for player in metadata['uncertain_players']:
            print(f"   - {player}")
        print()
    
    if metadata.get('warning'):
        print(f"⚠️  Warning: {metadata['warning']}")
        print()
    
    # Step 4: Validation
    print("✔️  Step 4: Validation")
    print("-" * 80)
    
    is_valid, reason = detector.validate_stored_teams(conn, session_date)
    
    team_a_size = len(team_a['guids'])
    team_b_size = len(team_b['guids'])
    total_players = team_a_size + team_b_size
    
    print(f"Total Players: {total_players}")
    print(f"Team Balance:  {team_a_size} vs {team_b_size}")
    
    balance_ratio = max(team_a_size, team_b_size) / min(team_a_size, team_b_size) if min(team_a_size, team_b_size) > 0 else 0
    
    if balance_ratio < 1.3:
        print(f"Balance:       ✅ Good ({balance_ratio:.2f}:1)")
    elif balance_ratio < 2.0:
        print(f"Balance:       ⚠️  Fair ({balance_ratio:.2f}:1)")
    else:
        print(f"Balance:       ❌ Poor ({balance_ratio:.2f}:1)")
    
    print()
    
    # Step 5: Offer to save
    print("💾 Step 5: Storage")
    print("-" * 80)
    
    if existing_teams:
        print("Teams already stored in database.")
        user_input = input("Overwrite with new detection? (y/N): ")
        if user_input.lower() == 'y':
            success = detector.store_detected_teams(conn, session_date, result)
            if success:
                print("✅ Teams updated successfully!")
            else:
                print("❌ Failed to update teams")
    else:
        print("No teams currently stored.")
        user_input = input("Store these teams? (Y/n): ")
        if user_input.lower() != 'n':
            success = detector.store_detected_teams(conn, session_date, result)
            if success:
                print("✅ Teams stored successfully!")
            else:
                print("❌ Failed to store teams")
    
    print()
    
    # Summary
    print("=" * 80)
    print("📈 SUMMARY")
    print("=" * 80)
    print(f"Session:     {session_date}")
    print(f"Quality:     {metadata.get('detection_quality', 'unknown').upper()}")
    print(f"Confidence:  {metadata.get('avg_confidence', 0):.1%}")
    print(f"Team A:      {team_a_size} players")
    print(f"Team B:      {team_b_size} players")
    print(f"Reliable:    {'✅ Yes' if is_reliable else '⚠️  No'}")
    print("=" * 80)
    
    conn.close()
    return True


def compare_with_old(session_date: str, db_path: str = "bot/etlegacy_production.db"):
    """Compare new detection with old stored teams"""
    
    print("🔄 Comparing with old detection method...")
    print()
    
    conn = sqlite3.connect(db_path)
    
    # Get old teams
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT team_name, player_guids, player_names
        FROM session_teams
        WHERE session_start_date LIKE ? AND map_name = 'ALL'
        ORDER BY team_name
        """,
        (f"{session_date}%",)
    )
    
    import json
    old_teams = {}
    for team_name, guids, names in cursor.fetchall():
        old_teams[team_name] = {
            'guids': set(json.loads(guids)),
            'names': set(json.loads(names))
        }
    
    if not old_teams:
        print("❌ No old teams to compare with")
        conn.close()
        return
    
    # Get new teams
    detector = TeamDetectorIntegration(db_path)
    result, _ = detector.detect_and_validate(conn, session_date)
    
    if not result:
        print("❌ New detection failed")
        conn.close()
        return
    
    new_teams = {
        'Team A': {
            'guids': set(result['Team A']['guids']),
            'names': set(result['Team A']['names'])
        },
        'Team B': {
            'guids': set(result['Team B']['guids']),
            'names': set(result['Team B']['names'])
        }
    }
    
    # Compare
    print("📊 Comparison Results:")
    print()
    
    # Find best match (teams might be swapped)
    matches = []
    for old_name in old_teams:
        for new_name in ['Team A', 'Team B']:
            overlap = len(old_teams[old_name]['guids'] & new_teams[new_name]['guids'])
            total = len(old_teams[old_name]['guids'] | new_teams[new_name]['guids'])
            similarity = overlap / total if total > 0 else 0
            matches.append((old_name, new_name, similarity, overlap, total - overlap))
    
    matches.sort(key=lambda x: x[2], reverse=True)
    
    best_matches = matches[:2]
    
    for old_name, new_name, similarity, same, diff in best_matches:
        print(f"{old_name} ≈ {new_name}")
        print(f"  Similarity: {similarity:.1%}")
        print(f"  Same players: {same}")
        print(f"  Different players: {diff}")
        print()
    
    # Overall assessment
    avg_similarity = sum(m[2] for m in best_matches) / len(best_matches)
    
    if avg_similarity > 0.9:
        print("✅ New detection matches old detection very closely!")
    elif avg_similarity > 0.7:
        print("⚠️  New detection differs somewhat from old detection")
    else:
        print("❌ New detection differs significantly from old detection")
    
    print()
    
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_advanced_team_detection.py <session_date> [--compare]")
        print("Example: python test_advanced_team_detection.py 2025-11-01")
        print("         python test_advanced_team_detection.py 2025-11-01 --compare")
        sys.exit(1)
    
    session_date = sys.argv[1]
    compare = "--compare" in sys.argv
    
    success = test_detection(session_date)
    
    if success and compare:
        print()
        compare_with_old(session_date)
