import sys
import os

# Use Agg backend for headless image generation
import matplotlib
matplotlib.use("Agg")

# Ensure project root is on sys.path so `import bot` works even if Python
# is executed from elsewhere or in a different environment.
import pathlib
ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.retro_viz import create_round_visualization


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_retro.py <input_stats_path> [output_png_path]")
        sys.exit(2)

    infile = sys.argv[1]
    outfile = sys.argv[2] if len(sys.argv) > 2 else os.path.join('tools', 'tmp', 'test_round.png')

    print(f"Reading stats: {infile}")
    fig = create_round_visualization(infile)
    fig.savefig(outfile, bbox_inches='tight')
    print(f"Saved {outfile}")


if __name__ == '__main__':
    main()
