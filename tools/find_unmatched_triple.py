p = r'g:\VisualStudio\Python\stats\bot\ultimate_bot.py'
with open(p, 'rb') as f:
    data = f.read().decode('utf-8','replace')
i = 0
n = len(data)
line = 1
state = None  # None, '"""' or "'''"
occurrences = []
while i < n:
    ch = data[i]
    if ch == '\n':
        line += 1
        i += 1
        continue
    # check triple double
    if data.startswith('"""', i):
        occurrences.append((line, '"""', state))
        if state is None:
            state = '"""'
        elif state == '"""':
            state = None
        else:
            # nested different triple
            occurrences.append((line, 'NESTED', state))
        i += 3
        continue
    if data.startswith("'''", i):
        occurrences.append((line, "'''", state))
        if state is None:
            state = "'''"
        elif state == "'''":
            state = None
        else:
            occurrences.append((line, 'NESTED', state))
        i += 3
        continue
    i += 1
# print occurrences and final state
for oc in occurrences[:200]:
    print(oc)
print('...')
print('FINAL_STATE=', state)
print('Total occurrences=', len(occurrences))
print('\nLast 40 occurrences:')
for oc in occurrences[-40:]:
    print(oc)
