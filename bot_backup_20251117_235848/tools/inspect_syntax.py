import linecache
p = r"g:\VisualStudio\Python\stats\bot\ultimate_bot.py"

s = open(p, 'r', encoding='utf-8').read()
try:
    compile(s, p, 'exec')
    print('COMPILE_OK')
except SyntaxError as e:
    lineno = e.lineno or 0
    print('SyntaxError:', e.msg, 'at line', lineno)
    start = max(1, lineno - 5)
    end = lineno + 5
    for i in range(start, end + 1):
        print(f"{i:5d}: {linecache.getline(p, i).rstrip()}")
    raise
