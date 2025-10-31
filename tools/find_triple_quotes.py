import sys
p = r'g:\VisualStudio\Python\stats\bot\ultimate_bot.py'
with open(p, 'rb') as f:
    s = f.read().decode('utf-8', 'replace')
lines = s.splitlines()
count = 0
for i, line in enumerate(lines, 1):
    idx = line.find('"""')
    if idx != -1:
        count += line.count('"""')
        print(f'{i}: {line.strip()}')
print('total triple double occurrences:', count)
# Also print triple single occurrences
count2 = 0
for i, line in enumerate(lines, 1):
    if "'''" in line:
        count2 += line.count("'''")
print('total triple single occurrences:', count2)
sys.exit(0)
