import tokenize, io
p = r"g:\\VisualStudio\\Python\\stats\\bot\\ultimate_bot.py"
s = open(p, 'r', encoding='utf-8').read()
for tok in tokenize.generate_tokens(io.StringIO(s).readline):
    ttype, tstring, (srow, scol), (erow, ecol), line = tok
    if ttype == tokenize.STRING:
        ts = tstring.lstrip()
        # crude detection: string token starts with f or F
        if ts and ts[0].lower() == 'f':
            if '{}' in tstring:
                print('Line', srow, ': contains empty {} in f-string ->', tstring[:200].replace('\n','\\n'))
