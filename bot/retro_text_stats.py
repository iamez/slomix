#!/usr/bin/env python3
"""
ET:Legacy Retro Text Stats Formatter
Two versions: Primary (matches viz) + Detailed (all extra data)
"""

from pathlib import Path
import sys

# Box-drawing characters for retro ASCII borders
BOX = {
    'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝',
    'h': '═', 'v': '║',
    'lt': '╠', 'rt': '╣', 'tt': '╦', 'bt': '╩', 'c': '╬'
}

# Discord color codes (for embed colors)
COLORS = {
    'cyan': '```ansi\n\x1b[36m',      # Cyan
    'green': '```ansi\n\x1b[32m',     # Green  
    'yellow': '```ansi\n\x1b[33m',    # Yellow
    'red': '```ansi\n\x1b[31m',       # Red
    'magenta': '```ansi\n\x1b[35m',   # Magenta
    'reset': '\x1b[0m\n```',
}

# Emojis for visual flair
EMOJI = {
    'kill': '💀',
    'death': '☠️',
    'damage': '💥',
    'medal': '🏆',
    'fire': '🔥',
    'target': '🎯',
    'shield': '🛡️',
    'time': '⏱️',
    'denied': '⛔',
    'support': '🏥',
    'weapon': '🔫',
    'grenade': '💣',
    'objective': '🎖️',
}


def create_box_line(width, left='╠', right='╣', fill='═'):
    """Create a box separator line"""
    return f"{left}{fill * (width - 2)}{right}"


def create_header(title, width=80):
    """Create a fancy header box"""
    lines = []
    lines.append(BOX['tl'] + BOX['h'] * (width - 2) + BOX['tr'])
    
    # Center the title
    padding = (width - 2 - len(title)) // 2
    line = BOX['v'] + ' ' * padding + title + ' ' * (width - 2 - padding - len(title)) + BOX['v']
    lines.append(line)
    
    lines.append(BOX['bl'] + BOX['h'] * (width - 2) + BOX['br'])
    return '\n'.join(lines)


def create_table_header(columns, widths):
    """Create a table header with columns"""
    header = BOX['v']
    for col, width in zip(columns, widths):
        header += f" {col.ljust(width)} {BOX['v']}"
    return header


def create_table_row(values, widths, alignments=None):
    """Create a table data row"""
    if alignments is None:
        alignments = ['<'] * len(values)
    
    row = BOX['v']
    for val, width, align in zip(values, widths, alignments):
        val_str = str(val)
        if align == '>':
            formatted = val_str.rjust(width)
        elif align == '^':
            formatted = val_str.center(width)
        else:
            formatted = val_str.ljust(width)
        row += f" {formatted} {BOX['v']}"
    return row


def parse_stats_file_complete(file_path):
    """Complete parser extracting ALL data fields"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    if len(lines) < 2:
        return None
    
    # Parse header
    header = lines[0].strip().split('\\')
    result = {
        'map_name': header[1] if len(header) > 1 else "Unknown",
        'config': header[2] if len(header) > 2 else "Unknown",
        'round_num': int(header[4]) if len(header) > 4 else 1,
        'duration': header[6] if len(header) > 6 else "Unknown",
        'actual_time': header[7] if len(header) > 7 else "Unknown",
        'players': []
    }
    
    for line in lines[1:]:
        if not line.strip():
            continue
        
        parts = line.strip().split('\\')
        if len(parts) < 2:
            continue
        
        guid = parts[0]
        name = parts[1]
        
        # Parse extended stats (TAB-separated after the weapon stats)
        if '\t' in line:
            sections = line.split('\t')
            
            # Parse weapon mask and weapon stats (before TAB)
            weapon_section = sections[0].split('\\')
            
            # Extended stats start after first TAB
            stats = sections[1:] if len(sections) > 1 else []
            
            try:
                player = {
                    'guid': guid[:8],
                    'name': name,
                    
                    # Basic combat (from TAB section)
                    'damage_given': int(stats[0]) if len(stats) > 0 else 0,
                    'damage_received': int(stats[1]) if len(stats) > 1 else 0,
                    'team_damage_given': int(stats[2]) if len(stats) > 2 else 0,
                    'team_damage_received': int(stats[3]) if len(stats) > 3 else 0,
                    'gibs': int(stats[4]) if len(stats) > 4 else 0,
                    'self_kills': int(stats[5]) if len(stats) > 5 else 0,
                    'team_kills': int(stats[6]) if len(stats) > 6 else 0,
                    'team_gibs': int(stats[7]) if len(stats) > 7 else 0,
                    'time_played_percent': float(stats[8]) if len(stats) > 8 else 0,
                    
                    # XP and streaks
                    'xp': int(stats[9]) if len(stats) > 9 else 0,
                    'killing_spree': int(stats[10]) if len(stats) > 10 else 0,
                    'death_spree': int(stats[11]) if len(stats) > 11 else 0,
                    
                    # Support/Objectives
                    'kill_assists': int(stats[12]) if len(stats) > 12 else 0,
                    'playtime_denied': int(stats[13]) if len(stats) > 13 else 0,
                    'headshot_kills': int(stats[14]) if len(stats) > 14 else 0,
                    'objectives_stolen': int(stats[15]) if len(stats) > 15 else 0,
                    'objectives_returned': int(stats[16]) if len(stats) > 16 else 0,
                    'dynamites_planted': int(stats[17]) if len(stats) > 17 else 0,
                    'dynamites_defused': int(stats[18]) if len(stats) > 18 else 0,
                    'times_revived': int(stats[19]) if len(stats) > 19 else 0,
                    
                    # Shooting stats
                    'bullets_fired': int(stats[20]) if len(stats) > 20 else 0,
                    'dpm': float(stats[21]) if len(stats) > 21 else 0,
                    'time_played_minutes': float(stats[22]) if len(stats) > 22 else 0,
                    'time_dead_ratio': float(stats[23]) if len(stats) > 23 else 0,
                    'time_dead_minutes': float(stats[24]) if len(stats) > 24 else 0,
                    'time_dead_total_minutes': float(stats[26]) if len(stats) > 26 else 0,
                    'kd_ratio': float(stats[27]) if len(stats) > 27 else 0,
                    
                    # Multikills
                    'double_kills': int(stats[29]) if len(stats) > 29 else 0,
                    'triple_kills': int(stats[30]) if len(stats) > 30 else 0,
                    'quad_kills': int(stats[31]) if len(stats) > 31 else 0,
                    'multi_kills': int(stats[32]) if len(stats) > 32 else 0,
                    'mega_kills': int(stats[33]) if len(stats) > 33 else 0,
                    
                    # Extra stats
                    'most_useful_kills': int(stats[34]) if len(stats) > 34 else 0,
                    'useless_kills': int(stats[35]) if len(stats) > 35 else 0,
                    'revives_given': int(stats[36]) if len(stats) > 36 else 0,
                    'health_given': int(stats[37]) if len(stats) > 37 else 0,
                    'ammo_given': int(stats[38]) if len(stats) > 38 else 0,
                }
                
                # Calculate derived stats
                player['kills'] = player.get('most_useful_kills', 0) + player.get('useless_kills', 0)
                player['deaths'] = int(stats[16]) if len(stats) > 16 and stats[16].isdigit() else 0
                
                # Efficiency
                total = player['kills'] + player['deaths']
                player['efficiency'] = (player['kills'] / total * 100) if total > 0 else 0
                
                # Accuracy (if we have bullets fired)
                if player['bullets_fired'] > 0:
                    # Estimate hits as damage_given / 15 (rough estimate)
                    hits = player['damage_given'] / 15
                    player['accuracy'] = (hits / player['bullets_fired'] * 100)
                else:
                    player['accuracy'] = 0
                
                result['players'].append(player)
            except Exception as e:
                print(f"Error parsing player: {e}")
                continue
    
    # Sort by kills
    result['players'].sort(key=lambda x: x.get('kills', 0), reverse=True)
    
    return result


# ============== VERSION 1: PRIMARY STATS (MATCHES VISUALIZATION) ==============

def create_primary_stats_text(data):
    """Create text version matching the visualization panels"""
    
    output = []
    
    # ========== HEADER ==========
    map_name = data['map_name'].upper()
    round_num = data['round_num']
    
    output.append("```ansi")
    output.append(create_header(f"═══ ET:LEGACY STATISTICS ═══", 80))
    output.append(create_header(f"{map_name} - ROUND {round_num}", 80))
    output.append("```")
    output.append("")
    
    # ========== MATCH SUMMARY ==========
    output.append("```ansi")
    output.append(f"\x1b[36m{EMOJI['fire']} MATCH SUMMARY {EMOJI['fire']}\x1b[0m")
    output.append(f"Map: {data['map_name']}")
    output.append(f"Round: {round_num}")
    output.append(f"Duration: {data.get('actual_time', 'Unknown')}")
    
    if data['players']:
        mvp = data['players'][0]
        output.append(f"\n{EMOJI['medal']} MVP: {mvp['name']}")
        output.append(f"{EMOJI['fire']} Best DPM: {mvp['name']} ({mvp['dpm']:.1f})")
        output.append(f"{EMOJI['kill']} Most Kills: {mvp['name']} ({mvp['kills']})")
    
    output.append("```")
    output.append("")
    
    # ========== TOP FRAGGERS ==========
    output.append(f"```ansi\n\x1b[33m{EMOJI['target']} TOP FRAGGERS {EMOJI['target']}\x1b[0m")
    
    top_10 = data['players'][:10]
    
    # Table header
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Rank', 'Player', 'Kills', 'Deaths', 'K/D', 'DPM']
    widths = [4, 30, 8, 8, 8, 10]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    # Table rows
    for idx, player in enumerate(top_10, 1):
        medal = '🥇' if idx == 1 else ('🥈' if idx == 2 else ('🥉' if idx == 3 else '  '))
        
        values = [
            f"{medal}{idx}",
            player['name'][:28],
            player['kills'],
            player['deaths'],
            f"{player['kd_ratio']:.2f}",
            f"{player['dpm']:.1f}"
        ]
        alignments = ['<', '<', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== COMBAT OVERVIEW (TOP 6) ==========
    output.append(f"```ansi\n\x1b[32m{EMOJI['fire']} COMBAT OVERVIEW {EMOJI['fire']}\x1b[0m")
    
    top_6 = data['players'][:6]
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Kills', 'Deaths', 'Gibs', 'DPM', 'Dmg', 'Eff%']
    widths = [20, 6, 7, 5, 7, 10, 8]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:18],
            player['kills'],
            player['deaths'],
            player['gibs'],
            f"{player['dpm']:.1f}",
            player['damage_given'],
            f"{player['efficiency']:.1f}%"
        ]
        alignments = ['<', '>', '>', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== DAMAGE BREAKDOWN ==========
    output.append(f"```ansi\n\x1b[31m{EMOJI['damage']} DAMAGE BREAKDOWN {EMOJI['damage']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Dmg Given', 'Dmg Recv', 'Gibs', 'Kills']
    widths = [25, 12, 12, 10, 10]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:23],
            player['damage_given'],
            player['damage_received'],
            player['gibs'],
            player['kills']
        ]
        alignments = ['<', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== SUPPORT PERFORMANCE ==========
    output.append(f"```ansi\n\x1b[32m{EMOJI['support']} SUPPORT PERFORMANCE {EMOJI['support']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Revives', 'Denied', 'Dead(m)', 'Health', 'Ammo']
    widths = [22, 10, 10, 10, 10, 10]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:20],
            player['revives_given'],
            player['playtime_denied'],
            f"{player['time_dead_total_minutes']:.1f}",
            player['health_given'],
            player['ammo_given']
        ]
        alignments = ['<', '>', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== PLAYTIME DENIED - KEY METRIC ==========
    output.append(f"```ansi\n\x1b[33m{EMOJI['denied']} PLAYTIME DENIED - KEY METRIC {EMOJI['denied']}\x1b[0m")
    
    # Sort by playtime denied
    top_deniers = sorted(data['players'][:10], key=lambda x: x['playtime_denied'], reverse=True)
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Rank', 'Player', 'Denied', 'Kills', 'Gibs', 'DPM']
    widths = [4, 28, 12, 10, 8, 10]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for idx, player in enumerate(top_deniers, 1):
        medal = '⭐' if idx == 1 else ('✨' if idx == 2 else ('💫' if idx == 3 else '  '))
        
        values = [
            f"{medal}{idx}",
            player['name'][:26],
            player['playtime_denied'],
            player['kills'],
            player['gibs'],
            f"{player['dpm']:.1f}"
        ]
        alignments = ['<', '<', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    
    return '\n'.join(output)


# ============== VERSION 2: DETAILED STATS (ALL REMAINING DATA) ==============

def create_detailed_stats_text(data):
    """Create detailed text with all remaining data fields"""
    
    output = []
    
    # ========== HEADER ==========
    output.append("```ansi")
    output.append(create_header(f"═══ DETAILED STATISTICS ═══", 80))
    output.append(create_header(f"ADVANCED METRICS & BREAKDOWNS", 80))
    output.append("```")
    output.append("")
    
    top_6 = data['players'][:6]
    
    # ========== ADVANCED COMBAT STATS ==========
    output.append(f"```ansi\n\x1b[35m{EMOJI['target']} ADVANCED COMBAT {EMOJI['target']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'HS', 'Acc%', 'Assists', 'Team K', 'Self K']
    widths = [22, 8, 8, 10, 10, 10]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:20],
            player['headshot_kills'],
            f"{player['accuracy']:.1f}%",
            player['kill_assists'],
            player['team_kills'],
            player['self_kills']
        ]
        alignments = ['<', '>', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== MULTIKILLS ==========
    output.append(f"```ansi\n\x1b[33m{EMOJI['fire']} MULTIKILL STreaks {EMOJI['fire']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Double', 'Triple', 'Quad', 'Multi', 'Mega']
    widths = [24, 8, 8, 8, 8, 8]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:22],
            player['double_kills'],
            player['triple_kills'],
            player['quad_kills'],
            player['multi_kills'],
            player['mega_kills']
        ]
        alignments = ['<', '>', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== OBJECTIVES & ENGINEERING ==========
    output.append(f"```ansi\n\x1b[36m{EMOJI['objective']} OBJECTIVES & ENGINEERING {EMOJI['objective']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Obj Take', 'Obj Ret', 'Dyna Plant', 'Dyna Def']
    widths = [26, 11, 11, 13, 13]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:24],
            player['objectives_stolen'],
            player['objectives_returned'],
            player['dynamites_planted'],
            player['dynamites_defused']
        ]
        alignments = ['<', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== KILL QUALITY ==========
    output.append(f"```ansi\n\x1b[32m{EMOJI['medal']} KILL QUALITY ANALYSIS {EMOJI['medal']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Total K', 'Useful', 'Useless', 'Best Spree', 'Worst']
    widths = [20, 8, 9, 9, 12, 10]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:18],
            player['kills'],
            player['most_useful_kills'],
            player['useless_kills'],
            player['killing_spree'],
            player['death_spree']
        ]
        alignments = ['<', '>', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== XP & PROGRESSION ==========
    output.append(f"```ansi\n\x1b[33m{EMOJI['medal']} XP & PROGRESSION {EMOJI['medal']}\x1b[0m")
    
    # Sort by XP
    top_xp = sorted(data['players'][:10], key=lambda x: x['xp'], reverse=True)
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Rank', 'Player', 'Total XP', 'K/D', 'Efficiency']
    widths = [4, 30, 15, 12, 12]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for idx, player in enumerate(top_xp, 1):
        values = [
            f"{idx}",
            player['name'][:28],
            player['xp'],
            f"{player['kd_ratio']:.2f}",
            f"{player['efficiency']:.1f}%"
        ]
        alignments = ['<', '<', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== TIME STATISTICS ==========
    output.append(f"```ansi\n\x1b[36m{EMOJI['time']} TIME STATISTICS {EMOJI['time']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Played(m)', 'Dead(m)', 'Dead%', 'Times Rev']
    widths = [24, 12, 12, 10, 12]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        values = [
            player['name'][:22],
            f"{player['time_played_minutes']:.1f}",
            f"{player['time_dead_total_minutes']:.1f}",
            f"{player['time_dead_ratio']:.1f}%",
            player['times_revived']
        ]
        alignments = ['<', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    output.append("")
    
    # ========== SHOOTING ACCURACY ==========
    output.append(f"```ansi\n\x1b[35m{EMOJI['weapon']} SHOOTING STATISTICS {EMOJI['weapon']}\x1b[0m")
    
    width = 78
    output.append(BOX['tl'] + BOX['h'] * width + BOX['tr'])
    
    cols = ['Player', 'Bullets', 'Est.Acc', 'HS', 'HS%']
    widths = [28, 12, 12, 10, 12]
    output.append(create_table_header(cols, widths))
    output.append(create_box_line(width + 2))
    
    for player in top_6:
        hs_percent = (player['headshot_kills'] / player['kills'] * 100) if player['kills'] > 0 else 0
        
        values = [
            player['name'][:26],
            player['bullets_fired'],
            f"{player['accuracy']:.1f}%",
            player['headshot_kills'],
            f"{hs_percent:.1f}%"
        ]
        alignments = ['<', '>', '>', '>', '>']
        output.append(create_table_row(values, widths, alignments))
    
    output.append(BOX['bl'] + BOX['h'] * width + BOX['br'])
    output.append("```")
    
    return '\n'.join(output)


# ============== MAIN FUNCTION ==============

def generate_text_stats(stats_file_path):
    """Generate both text versions"""
    
    # Parse the stats file
    data = parse_stats_file_complete(stats_file_path)
    
    if not data:
        return None, None
    
    # Generate both versions
    primary = create_primary_stats_text(data)
    detailed = create_detailed_stats_text(data)
    
    return primary, detailed


def save_text_stats(stats_file_path, output_dir='/home/claude'):
    """Save both text versions to files"""
    
    primary, detailed = generate_text_stats(stats_file_path)
    
    if not primary or not detailed:
        print("❌ Failed to generate text stats")
        return False
    
    # Save primary
    primary_path = f"{output_dir}/stats_primary.txt"
    with open(primary_path, 'w', encoding='utf-8') as f:
        f.write(primary)
    print(f"✅ Primary stats saved: {primary_path}")
    
    # Save detailed
    detailed_path = f"{output_dir}/stats_detailed.txt"
    with open(detailed_path, 'w', encoding='utf-8') as f:
        f.write(detailed)
    print(f"✅ Detailed stats saved: {detailed_path}")
    
    return True


# ============== MAIN ==============

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python retro_text_stats.py <stats_file.txt>")
        sys.exit(1)
    
    stats_file = sys.argv[1]
    save_text_stats(stats_file)
