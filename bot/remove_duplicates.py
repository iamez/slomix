#!/usr/bin/env python3
"""Remove duplicate helper methods from ultimate_bot.py"""

# Read the file
with open('g:/VisualStudio/Python/stats/bot/ultimate_bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove lines 5163-5336 (0-indexed: 5162-5335)
# This is the duplicate section
new_lines = lines[:5162] + lines[5336:]

# Write back
with open('g:/VisualStudio/Python/stats/bot/ultimate_bot.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f'✅ Removed {5336-5162} duplicate lines (5163-5336)')
print(f'✅ New file has {len(new_lines)} lines (was {len(lines)})')
