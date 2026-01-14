import py_compile
import glob
import sys

errs = 0
for f in glob.glob('**/*.py', recursive=True):
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        print('COMPILE_ERROR', f, e)
        errs += 1
print('COMPILE_DONE', errs)
if errs:
    sys.exit(2)
else:
    sys.exit(0)
