lines = open(
    'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt', 'r', encoding='utf-8'
).readlines()
vid_line = [l for l in lines if '^pvid' in l][0]
parts = vid_line.split('\t')
print(f'Total parts: {len(parts)}')
print(f'parts[35] full_selfkills: {repr(parts[35])}')
print(f'parts[36] repairs: {repr(parts[36])}')
if len(parts) > 37:
    print(f'parts[37]: {repr(parts[37])}')
