#!/usr/bin/env python3
"""Insert helper methods into ultimate_bot.py"""

# Read the main bot file
with open('g:/VisualStudio/Python/stats/bot/ultimate_bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Read the helper methods
with open('g:/VisualStudio/Python/stats/bot/helper_methods_to_insert.txt', 'r', encoding='utf-8') as f:
    insert = f.read()

# Find the marker (accounting for encoding issues)
markers = [
    '    # 🔄 BACKGROUND TASKS',
    '    # �🔄 BACKGROUND TASKS',
    '    # BACKGROUND TASKS',
]

found = False
for marker in markers:
    if marker in content:
        content = content.replace(marker, insert + '\n' + marker)
        found = True
        print(f'✅ Found marker: {repr(marker)}')
        break

if not found:
    print('❌ Could not find BACKGROUND TASKS marker')
    exit(1)

# Write back
with open('g:/VisualStudio/Python/stats/bot/ultimate_bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ Helper methods inserted successfully!')
