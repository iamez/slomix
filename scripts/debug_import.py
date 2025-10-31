import sys, importlib.util, os
print('cwd=', os.getcwd())
print('sys.path[0]=', sys.path[0])
print('find_spec=', importlib.util.find_spec('community_stats_parser'))
print('exists=', os.path.exists('community_stats_parser.py'))
print('abspath=', os.path.abspath('community_stats_parser.py'))
print('files in cwd:', [f for f in os.listdir('.') if f.endswith('.py')][:50])
