import tokenize, io
p = r"g:\VisualStudio\Python\stats\bot\ultimate_bot.py"
s = open(p, 'r', encoding='utf-8').read()
errors = []
for tok in tokenize.generate_tokens(io.StringIO(s).readline):
    ttype, tstring, (srow, scol), (erow, ecol), line = tok
    if ttype == tokenize.STRING:
        # Detect f-strings: start with f' or f" or F' or F" or f""" etc
        sstrip = tstring.lstrip('ubfrUBFR')
        if sstrip.startswith(('"', "'")) and ('f' in tstring[:3].lower()):
            # crude detection: if 'f' in prefix
            content = tstring
            # Count braces
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces != close_braces:
                errors.append((srow, content[:200].replace('\n','\\n'), open_braces, close_braces))

if not errors:
    print('No unbalanced f-string braces detected')
else:
    print('Found potential unbalanced f-strings:')
    for e in errors[:50]:
        print(f'Line {e[0]}: opens={e[2]} closes={e[3]} -> {e[1]}')
