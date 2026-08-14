#!/usr/bin/env python3
"""Rebuild the digit templates used by bot/services/supastats_image_reader.py.

The sheet is rendered in a fixed bitmap font, so ten averaged glyph templates
decode every numeric cell — but the templates have to come from somewhere, and
a naive "split a multi-digit cell into equal parts" bootstrap contaminates them
("1" is narrower than the rest, so equal splitting bleeds its neighbours into
it, which is exactly how "21" starts reading as "24").

So this bootstraps by SUPERVISED ALIGNMENT instead: the cell values come from
the database, so the digit IDENTITIES are known and only the cut points are
searched. That is what makes it converge — free decoding would have to guess
identities and cuts at once, so a bad template produces a bad cut which
produces a worse template (measured: it stalls at 35/42 and never recovers,
while alignment reaches 48/48 and free decode then follows at 47/48).

The generated file is therefore only ever as good as the labels, never as good
as the previous templates: a wrong template can shift a cut, but it can never
relabel a glyph. Each iteration prints the free-decode accuracy so a regression
is visible, and the fixtures in tests/unit/test_supastats_image_reader.py pin
the result against database-verified values.

Usage (dev only, read-only):
    python scripts/build_supastats_glyphs.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.services import supastats_image_reader as reader  # noqa: E402

OUT_FILE = ROOT / "bot" / "services" / "data" / "supastats_glyphs.json"
TEMPLATE_SIZE = reader.TEMPLATE_SHAPE

# Per-map kills for gaming session 144 (2026-08-11), taken from the database
# and independently confirmed against the sheet on 2026-08-14. Row order is the
# sheet's: RED players top to bottom, then BLUE. The trailing value is the
# player's session total, which lives in the summary column — that column has a
# lighter conditional-format fill, so the same glyph renders with noticeably
# less contrast there. Training on both contexts is what stops a summary "9"
# from scoring closer to "0" than to itself.
LABELS = {
    "screenshots/supastats12-8-2026.png": [
        [21, 10, 44, 11, 18, 14, 3, 121],
        [18, 7, 29, 12, 12, 12, 2, 92],
        [9, 5, 15, 7, 9, 6, 3, 54],
        [9, 13, 21, 9, 21, 8, 1, 82],
        [13, 12, 25, 6, 13, 14, 1, 84],
        [8, 16, 17, 7, 12, 11, 3, 74],
    ],
}


def _cells(path: str):
    """Yield (row_index, col_index, ink strip) for the kills block."""
    arr = np.array(Image.open(ROOT / path).convert("RGB"))
    edges, y0, n_rows, left = reader._detect_geometry(arr)  # noqa: SLF001 — this IS the reader's geometry
    n_maps = len(edges) - 1

    roles = []
    for row in range(n_rows):
        label = reader._classify(reader._modal_rgb(reader._label_cell(arr, left, y0, row).astype(int)))  # noqa: SLF001
        header = any(
            reader._classify(reader._modal_rgb(reader._cell(arr, edges, y0, c, row).astype(int)))  # noqa: SLF001
            in ("RED", "BLUE")
            for c in range(n_maps)
        )
        roles.append("HEADER" if header and label == "WHITE" else label)

    headers = [i for i, r in enumerate(roles) if r == "HEADER"]
    start, stop = headers[1], headers[2] if len(headers) > 2 else n_rows
    player_rows = [r for r in range(start + 1, stop) if roles[r] in ("RED", "BLUE")]
    for idx, row in enumerate(player_rows):
        patches = [reader._cell(arr, edges, y0, col, row) for col in range(n_maps)]  # noqa: SLF001
        patches.append(reader._summary_cell(arr, left, y0, row))  # noqa: SLF001 — the session total
        for col, patch in enumerate(patches):
            value = reader._inkness(patch)  # noqa: SLF001
            if value is None:
                continue
            strip = reader._crop_ink(value)  # noqa: SLF001
            if strip is not None:
                yield idx, col, strip


def _crop(part):
    """Crop to ink in both axes — see the reader's score_at for why width matters."""
    return reader._crop_ink(part)  # noqa: SLF001


def _align(strip, digits: str, templates) -> list[tuple[int, int]] | None:
    """Best cut points for a strip whose digits are ALREADY KNOWN.

    This is the crux of the bootstrap. Free decoding has to guess both the cut
    points and the identities at once, so a bad template produces a bad cut
    which produces a worse template. Here the identities come from the label,
    so only the cuts are searched — supervised alignment, which converges even
    from a rough seed. Cells whose digits we do not know are never used.
    """
    n = len(digits)
    width = strip.shape[1]
    # best[i][k] = score of covering strip[i:] with digits[k:]
    best = [[(-1e9, []) for _ in range(n + 1)] for _ in range(width + 1)]
    best[width][n] = (0.0, [])
    for i in range(width, -1, -1):
        for k in range(n - 1, -1, -1):
            for size in range(reader.MIN_GLYPH_WIDTH, reader.MAX_GLYPH_WIDTH + 1):
                if i + size > width:
                    continue
                tail = best[i + size][k + 1]
                if tail[0] <= -1e8:
                    continue
                cropped = _crop(strip[:, i:i + size])
                if cropped is None:
                    continue
                tpl = templates.get(digits[k])
                if tpl is None:
                    # A digit we have never seen scores neutrally: its
                    # neighbours pin the alignment and it gets its segment by
                    # elimination. This is how "0" and "4" — which never appear
                    # alone in the labelled block — are learned at all.
                    score = tail[0]
                else:
                    vec = reader._normalise(cropped)  # noqa: SLF001
                    score = float(np.dot(vec.ravel(), tpl.ravel()) / vec.size) + tail[0]
                if score > best[i][k][0]:
                    best[i][k] = (score, [(i, size)] + tail[1])
    return best[0][0][1] or None


def bootstrap(rounds: int = 6) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    templates = dict(reader._templates())  # noqa: SLF001 — seed from the current file
    all_widths = dict(reader._template_widths())  # noqa: SLF001
    for iteration in range(rounds):
        samples: dict[str, list[tuple[np.ndarray, int]]] = {}
        aligned = total = 0
        for path, expected in LABELS.items():
            for row, col, strip in _cells(path):
                if row >= len(expected) or col >= len(expected[row]):
                    continue
                want = str(expected[row][col])
                total += 1
                cuts = _align(strip, want, templates)
                if not cuts:
                    continue
                aligned += 1
                for (start, size), digit in zip(cuts, want):
                    cropped = _crop(strip[:, start:start + size])
                    if cropped is not None:
                        samples.setdefault(digit, []).append(
                            (reader._normalise(cropped), cropped.shape[1])  # noqa: SLF001
                        )
        # Free-decode the same cells to measure what the reader will actually do.
        correct = sum(
            1
            for path, expected in LABELS.items()
            for row, col, strip in _cells(path)
            if row < len(expected) and col < len(expected[row])
            and reader._read_number_strip(strip)[0] == str(expected[row][col])  # noqa: SLF001
        )
        print(f"  iteration {iteration + 1}: aligned {aligned}/{total} labelled cells, "
              f"free decode {correct}/{total} correct "
              f"({sum(len(v) for v in samples.values())} glyph samples)")
        if not samples:
            break
        rebuilt = {d: np.mean([s for s, _ in v], axis=0) for d, v in samples.items()}
        widths = {d: float(np.mean([w for _, w in v])) for d, v in samples.items()}
        # Keep any digit the new pass did not observe rather than losing it.
        templates = {**templates, **rebuilt}
        all_widths = {**all_widths, **widths}
    return templates, all_widths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the template file")
    args = parser.parse_args()

    print("Bootstrapping supastats glyph templates from verified DB values...")
    templates, widths = bootstrap()

    payload = {
        "version": 1,
        "template_size": list(TEMPLATE_SIZE),
        "note": (
            "Normalised (zero-mean/unit-std) inkness templates for the supastats sheet font. "
            "Bootstrapped by scripts/build_supastats_glyphs.py from cells whose decoded value "
            "matches the database — see that script for why equal-width splitting is unsafe."
        ),
        "glyphs": {d: [[round(float(x), 4) for x in row] for row in t]
                   for d, t in sorted(templates.items())},
        "widths": {d: round(w, 2) for d, w in sorted(widths.items())},
    }
    if args.write:
        OUT_FILE.write_text(json.dumps(payload, indent=1))
        print(f"Wrote {OUT_FILE.relative_to(ROOT)} ({len(payload['glyphs'])} glyphs)")
    else:
        print(f"Dry run — {len(payload['glyphs'])} glyphs built. Re-run with --write to save.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
