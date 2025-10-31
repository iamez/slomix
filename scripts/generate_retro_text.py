import sys
import os
import pathlib

# Ensure project root on sys.path
ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.retro_text_stats import generate_text_stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_retro_text.py <input_stats_path> [detailed_out.txt]")
        sys.exit(2)

    infile = sys.argv[1]
    detailed_out = sys.argv[2] if len(sys.argv) > 2 else os.path.join('tools', 'tmp', 'retro_detailed.txt')

    primary, detailed = generate_text_stats(infile)
    print("--- Primary ---")
    print(primary)
    print("--- Detailed saved to:", detailed_out, "---")
    with open(detailed_out, 'w', encoding='utf-8') as f:
        f.write(detailed)


if __name__ == '__main__':
    main()
