#!/usr/bin/env python3
"""slomix_retro.py — Unified retro visualization tool for Slomix.

Consolidates 3 retro scripts into a single CLI with subcommands:
  slomix_retro.py viz <input_stats> [output_png]
  slomix_retro.py text <input_stats> [detailed_out]
  slomix_retro.py test [--input FILE]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Use Agg backend for headless image generation
import matplotlib
matplotlib.use("Agg")

# Setup sys.path and load .env
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Optional imports - retro visualization modules may not be available
try:
    from bot.retro_viz import create_round_visualization
except ImportError:
    create_round_visualization = None

try:
    from bot.retro_text_stats import generate_text_stats
except ImportError:
    generate_text_stats = None

# ============================================================================
# SUBCOMMAND: viz
# ============================================================================

def cmd_viz(args):
    if create_round_visualization is None:
        print("ERROR: retro visualization module not available. Archived scripts in scripts/archive/")
        return 1

    infile = args.input
    outfile = args.output or os.path.join('tools', 'tmp', 'test_round.png')

    print(f"Reading stats: {infile}")
    fig = create_round_visualization(infile)
    fig.savefig(outfile, bbox_inches='tight')
    print(f"Saved {outfile}")
    return 0

# ============================================================================
# SUBCOMMAND: text
# ============================================================================

def cmd_text(args):
    if generate_text_stats is None:
        print("ERROR: retro text stats module not available. Archived scripts in scripts/archive/")
        return 1

    infile = args.input
    detailed_out = args.output or os.path.join('tools', 'tmp', 'retro_detailed.txt')

    primary, detailed = generate_text_stats(infile)
    print("--- Primary ---")
    print(primary)
    print("--- Detailed saved to:", detailed_out, "---")
    with open(detailed_out, 'w', encoding='utf-8') as f:
        f.write(detailed)
    return 0

# ============================================================================
# SUBCOMMAND: test
# ============================================================================

def cmd_test(args):
    if create_round_visualization is None or generate_text_stats is None:
        print("ERROR: retro visualization modules not available. Archived scripts in scripts/archive/")
        return 1

    infile = args.input
    png_out = os.path.join('tools', 'tmp', 'retro_test.png')
    detailed_out = os.path.join('tools', 'tmp', 'retro_test_detailed.txt')

    print('Input:', infile)
    if not os.path.exists(infile):
        print('ERROR: input file not found:', infile)
        return 2

    # Create PNG
    try:
        fig = create_round_visualization(infile)
        fig.savefig(png_out, bbox_inches='tight')
        print('Saved PNG:', png_out)
    except Exception as e:
        print('PNG generation failed:', e)
        return 3

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
        return 4

    # Verify outputs
    ok = os.path.exists(png_out) and os.path.exists(detailed_out)
    print('\nVerification:', 'OK' if ok else 'FAILED')
    return 0 if ok else 5

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified retro visualization tool for Slomix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/slomix_retro.py viz local_stats/2025-10-28-233754-etl_adlernest-round-1.txt
  python tools/slomix_retro.py viz stats.txt output.png
  python tools/slomix_retro.py text stats.txt detailed.txt
  python tools/slomix_retro.py test
  python tools/slomix_retro.py test --input local_stats/some-round.txt
        """
    )

    subs = parser.add_subparsers(dest='command', required=True, help='Retro subcommand')

    # VIZ subcommand
    sub = subs.add_parser('viz', help='Generate retro PNG visualization from stats file')
    sub.add_argument('input', help='Input stats file path')
    sub.add_argument('output', nargs='?', default=None, help='Output PNG path (default: tools/tmp/test_round.png)')
    sub.set_defaults(func=cmd_viz)

    # TEXT subcommand
    sub = subs.add_parser('text', help='Generate retro text stats from stats file')
    sub.add_argument('input', help='Input stats file path')
    sub.add_argument('output', nargs='?', default=None, help='Output detailed text path (default: tools/tmp/retro_detailed.txt)')
    sub.set_defaults(func=cmd_text)

    # TEST subcommand
    sub = subs.add_parser('test', help='Run retro test (both viz and text) on a sample file')
    sub.add_argument('--input', default=os.path.join('local_stats', '2025-10-28-233754-etl_adlernest-round-1.txt'),
                     help='Input stats file (default: local_stats/2025-10-28-233754-etl_adlernest-round-1.txt)')
    sub.set_defaults(func=cmd_test)

    args = parser.parse_args()
    logger.info("Script started: %s with command: %s", __file__, args.command)

    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
