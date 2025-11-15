#!/usr/bin/env python3
"""
Team History Helper Functions

Utility functions for querying and displaying team history data.
These can be imported and used by bot commands or analysis scripts.
"""

import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class TeamHistoryManager:
    """Manages team history queries and analytics"""
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
    
    def get_lineup_stats(self, lineup_id: int) -> Optional[Dict]:
        """
        Get detailed stats for a specific lineup.
        
        Returns:
            Dict with lineup info, roster, and performance stats
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM team_lineups WHERE id = ?
        """, (lineup_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        lineup = dict(row)
        lineup['player_guids'] = json.loads(lineup['player_guids'])
        
        # Get player names
        guids = lineup['player_guids']
        placeholders = ','.join('?' * len(guids))
        cursor.execute(f"""
            SELECT guid, alias
            FROM player_aliases
            WHERE guid IN ({placeholders})
            AND last_seen = (SELECT MAX(last_seen) FROM player_aliases pa2 WHERE pa2.guid = player_aliases.guid)
        """, guids)
        
        names = {row['guid']: row['alias'] for row in cursor.fetchall()}
        lineup['player_names'] = [names.get(g, g) for g in guids]
        
        # Calculate win rate
        total = lineup['total_wins'] + lineup['total_losses'] + lineup['total_ties']
        lineup['win_rate'] = (lineup['total_wins'] / total * 100) if total > 0 else 0
        
        conn.close()
        return lineup
    
    def get_lineup_sessions(self, lineup_id: int) -> List[Dict]:
        """Get all sessions played by a lineup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sr.*,
                   CASE 
                       WHEN sr.team_1_lineup_id = ? THEN sr.team_1_name
                       ELSE sr.team_2_name
                   END as this_team,
                   CASE 
                       WHEN sr.team_1_lineup_id = ? THEN sr.team_2_name
                       ELSE sr.team_1_name
                   END as opponent_team,
                   CASE 
                       WHEN sr.team_1_lineup_id = ? THEN sr.team_1_score
                       ELSE sr.team_2_score
                   END as this_score,
                   CASE 
                       WHEN sr.team_1_lineup_id = ? THEN sr.team_2_score
                       ELSE sr.team_1_score
                   END as opponent_score
            FROM session_results sr
            WHERE sr.team_1_lineup_id = ? OR sr.team_2_lineup_id = ?
            ORDER BY sr.session_date DESC
        """, (lineup_id, lineup_id, lineup_id, lineup_id, lineup_id, lineup_id))
        
        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return sessions
    
    def find_similar_lineups(self, player_guids: List[str], min_overlap: int = 3) -> List[Dict]:
        """
        Find lineups with significant player overlap.
        
        Args:
            player_guids: List of player GUIDs to match
            min_overlap: Minimum number of shared players
        
        Returns:
            List of matching lineups with overlap count
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM team_lineups")
        
        similar = []
        player_set = set(player_guids)
        
        for row in cursor.fetchall():
            lineup_guids = set(json.loads(row['player_guids']))
            overlap = len(player_set & lineup_guids)
            
            if overlap >= min_overlap:
                lineup = dict(row)
                lineup['overlap_count'] = overlap
                lineup['overlap_percent'] = overlap / max(len(player_set), len(lineup_guids)) * 100
                similar.append(lineup)
        
        conn.close()
        return sorted(similar, key=lambda x: x['overlap_count'], reverse=True)
    
    def get_head_to_head(self, lineup1_id: int, lineup2_id: int) -> Dict:
        """
        Get head-to-head record between two lineups.
        
        Returns:
            Dict with wins/losses/ties for each lineup
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM session_results
            WHERE (team_1_lineup_id = ? AND team_2_lineup_id = ?)
               OR (team_1_lineup_id = ? AND team_2_lineup_id = ?)
            ORDER BY session_date DESC
        """, (lineup1_id, lineup2_id, lineup2_id, lineup1_id))
        
        matches = [dict(row) for row in cursor.fetchall()]
        
        lineup1_wins = 0
        lineup2_wins = 0
        ties = 0
        
        for match in matches:
            if match['winner'] == 'TIE':
                ties += 1
            elif (match['team_1_lineup_id'] == lineup1_id and match['team_1_score'] > match['team_2_score']) or \
                 (match['team_2_lineup_id'] == lineup1_id and match['team_2_score'] > match['team_1_score']):
                lineup1_wins += 1
            else:
                lineup2_wins += 1
        
        conn.close()
        
        return {
            'total_matches': len(matches),
            'lineup1_wins': lineup1_wins,
            'lineup2_wins': lineup2_wins,
            'ties': ties,
            'matches': matches
        }
    
    def get_recent_lineups(self, days: int = 30, min_sessions: int = 1) -> List[Dict]:
        """Get lineups active in recent period"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Check if team_lineups table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_lineups'")
        if not cursor.fetchone():
            # Fallback: Use session_teams instead
            cursor.execute("""
                SELECT 
                    team_name,
                    player_names,
                    player_guids,
                    session_start_date as last_seen,
                    1 as total_sessions,
                    created_at as first_seen
                FROM session_teams
                WHERE session_start_date >= ?
                ORDER BY session_start_date DESC
                LIMIT 50
            """, (cutoff_date,))
            results = cursor.fetchall()
            conn.close()
            return results
        
        cursor.execute("""
            SELECT * FROM team_lineups
            WHERE last_seen >= ?
            AND total_sessions >= ?
            ORDER BY last_seen DESC, total_sessions DESC
        """, (cutoff_date, min_sessions))
        
        lineups = []
        for row in cursor.fetchall():
            lineup = dict(row)
            lineup['player_guids'] = json.loads(lineup['player_guids'])
            lineups.append(lineup)
        
        conn.close()
        return lineups
    
    def get_best_lineups(self, min_sessions: int = 3, limit: int = 10) -> List[Dict]:
        """Get top performing lineups by win rate"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT *,
                   CAST(total_wins AS FLOAT) / (total_wins + total_losses + total_ties) * 100 as win_rate
            FROM team_lineups
            WHERE (total_wins + total_losses + total_ties) >= ?
            ORDER BY win_rate DESC, total_wins DESC
            LIMIT ?
        """, (min_sessions, limit))
        
        lineups = []
        for row in cursor.fetchall():
            lineup = dict(row)
            lineup['player_guids'] = json.loads(lineup['player_guids'])
            lineups.append(lineup)
        
        conn.close()
        return lineups


if __name__ == "__main__":
    # Example usage
    manager = TeamHistoryManager()
    
    print("🏆 Best Performing Lineups (min 1 session):")
    print("="*60)
    
    best = manager.get_best_lineups(min_sessions=1, limit=5)
    for i, lineup in enumerate(best, 1):
        print(f"\n{i}. Lineup #{lineup['id']} ({lineup['player_count']} players)")
        print(f"   Sessions: {lineup['total_sessions']}")
        print(f"   Record: {lineup['total_wins']}W - {lineup['total_losses']}L - {lineup['total_ties']}T")
        print(f"   Win Rate: {lineup['win_rate']:.1f}%")
        print(f"   Active: {lineup['first_seen']} to {lineup['last_seen']}")
    
    print("\n" + "="*60)
