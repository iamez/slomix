import sys
import os
import pathlib

# Headless backend
import matplotlib
matplotlib.use('Agg')

# Ensure project root on sys.path
ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.retro_viz import create_round_visualization
from bot.retro_text_stats import generate_text_stats


def main():
    infile = os.path.join('local_stats', '2025-10-28-233754-etl_adlernest-round-1.txt')
    png_out = os.path.join('tools', 'tmp', 'retro_test.png')
    detailed_out = os.path.join('tools', 'tmp', 'retro_test_detailed.txt')

    print('Input:', infile)
    if not os.path.exists(infile):
        print('ERROR: input file not found:', infile)
        sys.exit(2)

    # Create PNG
    try:
        fig = create_round_visualization(infile)
        fig.savefig(png_out, bbox_inches='tight')
        print('Saved PNG:', png_out)
    except Exception as e:
        print('PNG generation failed:', e)
        sys.exit(3)

    # Create text
    try:
        primary, detailed = generate_text_stats(infile)
        print('\n--- Primary ---\n')
        print(primary)
        with open(detailed_out, 'w', encoding='utf-8') as f:
            f.write(detailed or '')
        print('\nSaved detailed text to:', detailed_out)
    except Exception as e:
        print('Text generation failed:', e)
        sys.exit(4)

    # Verify outputs
    ok = os.path.exists(png_out) and os.path.exists(detailed_out)
    print('\nVerification:', 'OK' if ok else 'FAILED')
    sys.exit(0 if ok else 5)


if __name__ == '__main__':
    main()
