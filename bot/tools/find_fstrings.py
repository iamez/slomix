import re
p = r"g:\VisualStudio\Python\stats\bot\ultimate_bot.py"
s = open(p,'r',encoding='utf-8').read()
for m in re.finditer(r"f(\"|\')", s):
    start = m.start()
    # show surrounding 120 chars
    seg = s[max(0,start-60):start+120]
    # find line number
    lineno = s.count('\n',0,start)+1
    print(lineno, seg.replace('\n','\\n'))
