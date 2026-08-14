"""Read a supastats spreadsheet screenshot into structured data.

Supa reviews the demos every morning and posts a screenshot of his sheet. That
sheet is an INDEPENDENT measurement of the same night we parse from the stats
files, which makes it the best external audit we have — a manual comparison on
2026-08-14 both cleared a suspected scoring regression and found 17 genuinely
inverted historical rounds. This module turns that screenshot into numbers so
the comparison can run automatically.

Pure and dependency-light on purpose: Pillow + numpy only (both already used by
session_graph_generator), no OCR engine. The sheet is rendered at a fixed zoom
with a pixel-regular grid and a fixed bitmap font, so cells are segmented from
detected anchors and digits are matched against templates built from that same
font (bot/services/data/supastats_glyphs.json). At 9px glyph height this is both
more accurate and more predictable than a general OCR engine.

Everything is anchor-DETECTED rather than hardcoded, and any deviation from the
expected geometry raises UnsupportedScreenshot. A wrong number is far worse than
a refusal here: it would send the owner chasing a discrepancy that only exists
in the reader.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --- sheet constants (measured from the reference screenshots) --------------
GRID_RGB = (225, 225, 225)      # 1px cell gridline
SEPARATOR_RGB = (199, 199, 199)  # 4px strip between the summary and map columns
RED_RGB = (234, 153, 153)        # header fill: RED team won this map
BLUE_RGB = (164, 194, 244)       # header fill: BLUE team won this map
ROUND_ROW_RGB = (204, 204, 204)  # "Round 1" / "Round 2" duration rows
WHITE_RGB = (255, 255, 255)

COLUMN_PITCH = 60
ROW_PITCH = 17
PITCH_TOLERANCE = 1              # px; anything looser is a different zoom level
MIN_GLYPH_WIDTH = 3              # narrowest digit ("1") at this zoom
MAX_GLYPH_WIDTH = 7              # widest digit
MIN_DIGIT_SCORE = 0.45           # mean template correlation below this = unreadable
# Cost charged per digit the segmentation adds. Without it the search is biased
# toward more digits (summing more scores always wins), which turns "21" into
# "241"; a digit must now out-score this to be worth cutting.
DIGIT_COST = 0.55
INK_THRESHOLD = 0.35             # fraction of a cell's max contrast that counts as ink
MIN_CONTRAST = 60                # below this a cell is considered empty

TEMPLATE_SHAPE = (10, 6)         # canvas every glyph is scaled to before matching
WIDTH_PENALTY = 0.12             # score cost per pixel of width deviation (separates 1 from 4)
_GLYPH_FILE = Path(__file__).parent / "data" / "supastats_glyphs.json"


class UnsupportedScreenshot(Exception):
    """The image is not a supastats sheet at the expected zoom.

    Raised instead of guessing. The caller reports "I cannot read this image",
    which is honest; silently mis-reading it would manufacture discrepancies.
    """


@dataclass
class PlayerRow:
    name: str | None
    team: str                    # "RED" | "BLUE"
    values: list[int | None]     # one per map column
    total: int | None            # the summary column


@dataclass
class ParsedSheet:
    session_date: str | None
    map_count: int
    winners: list[str | None]            # "RED" | "BLUE" per map column
    dpm: list[PlayerRow] = field(default_factory=list)
    kills: list[PlayerRow] = field(default_factory=list)
    effort_present: bool = False
    round1_seconds: list[int | None] = field(default_factory=list)
    round2_seconds: list[int | None] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def kills_checksum_ok(self) -> bool:
        """Per-map kills must sum to the player's session total.

        The sheet computes the total itself, so this is a checksum the reader
        did not produce — if it fails, the digits were misread and the result
        must not be compared against anything.
        """
        for row in self.kills:
            if row.total is None or any(v is None for v in row.values):
                return False
            if sum(v for v in row.values if v is not None) != row.total:
                return False
        return bool(self.kills)


# --- geometry ---------------------------------------------------------------

def _dark_lines(sums, axis_len: int) -> list[int]:
    """Indices that are consistently darker than both neighbours = gridlines.

    The gridline is drawn as a MULTIPLY over the cell fill, so it is not a
    constant colour (over a red cell it reads (207,137,137), not (225,225,225)).
    Relative darkness is the only detector that survives the tinted cells.
    """
    out = []
    for i in range(1, len(sums) - 1):
        darker = (sums[i] < sums[i - 1] - 8) & (sums[i] < sums[i + 1] - 8)
        if darker.mean() > 0.6:
            out.append(i)
    return out


def _detect_geometry(arr) -> tuple[list[int], int, int, tuple[int, int, int]]:
    """Return (map column edges, first row offset, row count, left column edges).

    ``left`` is ``(name_start, name_end, summary_end)``: the label column holds
    the player name, the summary column holds the session total (and the sheet
    date on header rows). They must be read separately — the summary column
    carries its own conditional-format gradient, so sampling both together
    misreads a player's team colour as the gradient's yellow.

    Raises UnsupportedScreenshot when the detected pitch is not the expected
    60x17 — i.e. a different browser zoom, DPI or theme.
    """
    import numpy as np

    sums = arr.astype(int).sum(axis=2)
    v_lines = _dark_lines(sums.T, arr.shape[0])
    h_lines = _dark_lines(sums, arr.shape[1])

    sep_mask = np.all(arr == np.array(SEPARATOR_RGB), axis=2).mean(axis=0)
    sep_cols = [x for x in range(arr.shape[1]) if sep_mask[x] > 0.5]
    if not sep_cols:
        raise UnsupportedScreenshot("separator strip not found — not a supastats sheet")
    sep_start, sep_end = min(sep_cols), max(sep_cols)

    # The first map column starts right after the separator; the remaining
    # edges are the gridlines to its right.
    edges = [sep_end + 1] + [x for x in v_lines if x > sep_end]
    if len(edges) < 2:
        raise UnsupportedScreenshot("no map columns found")
    gaps = {edges[i + 1] - edges[i] for i in range(1, len(edges) - 1)}
    if gaps and any(abs(g - COLUMN_PITCH) > PITCH_TOLERANCE for g in gaps):
        raise UnsupportedScreenshot(
            f"unexpected column pitch {sorted(gaps)} (expected {COLUMN_PITCH})"
        )

    if not h_lines:
        raise UnsupportedScreenshot("no row gridlines found")
    row_gaps = {h_lines[i + 1] - h_lines[i] for i in range(len(h_lines) - 1)}
    # Blank rows draw no line, so gaps are multiples of the pitch.
    if any(g % ROW_PITCH for g in row_gaps):
        raise UnsupportedScreenshot(
            f"unexpected row pitch {sorted(row_gaps)} (expected multiples of {ROW_PITCH})"
        )

    left_lines = [x for x in v_lines if x < sep_end]
    if len(left_lines) < 2:
        raise UnsupportedScreenshot("label/summary columns not found")
    # The summary column ends where the separator strip begins — including any
    # of the strip would drag its grey into the cell's modal background and
    # clip the last digit.
    left = (left_lines[0], left_lines[1], sep_start)

    y0 = h_lines[0] % ROW_PITCH
    n_rows = (arr.shape[0] - y0) // ROW_PITCH
    return edges, y0, n_rows, left


def _rows_slice(y0, row: int) -> tuple[int, int]:
    return y0 + ROW_PITCH * row + 1, y0 + ROW_PITCH * (row + 1) - 1


def _cell(arr, edges, y0, col: int, row: int):
    ya, yb = _rows_slice(y0, row)
    return arr[ya:yb, edges[col] + 1:edges[col + 1] - 1]


def _label_cell(arr, left, y0, row: int):
    """The player-name column only — never the summary column beside it."""
    ya, yb = _rows_slice(y0, row)
    return arr[ya:yb, left[0] + 1:left[1]]


def _summary_cell(arr, left, y0, row: int):
    """Session total per player; on a block header row, the sheet date."""
    ya, yb = _rows_slice(y0, row)
    return arr[ya:yb, left[1] + 1:left[2]]


def _modal_rgb(patch) -> tuple[int, int, int]:
    flat = patch.reshape(-1, patch.shape[-1])
    return Counter(map(tuple, flat.tolist())).most_common(1)[0][0]


def _classify(rgb) -> str:
    for name, ref in (("RED", RED_RGB), ("BLUE", BLUE_RGB),
                      ("ROUND", ROUND_ROW_RGB), ("WHITE", WHITE_RGB)):
        if all(abs(int(a) - int(b)) <= 6 for a, b in zip(rgb, ref)):
            return name
    return "OTHER"


# --- digits -----------------------------------------------------------------

@lru_cache(maxsize=1)
def _glyph_file() -> dict[str, Any]:
    return json.loads(_GLYPH_FILE.read_text())


@lru_cache(maxsize=1)
def _templates() -> dict[str, Any]:
    import numpy as np

    return {d: np.array(v, dtype=float) for d, v in _glyph_file()["glyphs"].items()}


@lru_cache(maxsize=1)
def _template_widths() -> dict[str, float]:
    """Natural pixel width of each glyph in the sheet's font."""
    return {d: float(w) for d, w in _glyph_file().get("widths", {}).items()}


def _inkness(patch):
    """Cell -> [0,1] map where 1 is the darkest ink, 0 is the background.

    Normalising against the cell's own background is what makes one template
    set work across the sheet's conditional-format gradient: the glyph shape is
    identical everywhere, only the fill behind it changes.
    """
    import numpy as np

    sub = patch.astype(float)
    bg = np.array(_modal_rgb(patch.astype(int)), dtype=float)
    dist = np.abs(sub - bg).sum(axis=2)
    peak = dist.max()
    if peak < MIN_CONTRAST:
        return None
    return dist / peak


def _crop_ink(value):
    import numpy as np

    mask = value > INK_THRESHOLD
    cols = np.where(mask.any(axis=0))[0]
    rows = np.where(mask.any(axis=1))[0]
    if not len(cols) or not len(rows):
        return None
    return value[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


def _normalise(patch):
    """Scale a glyph to the template canvas and standardise its contrast."""
    import numpy as np
    from PIL import Image

    img = Image.fromarray((np.clip(patch, 0, 1) * 255).astype("uint8")).resize(
        (TEMPLATE_SHAPE[1], TEMPLATE_SHAPE[0]), Image.BILINEAR
    )
    vec = np.asarray(img, dtype=float) / 255.0
    return (vec - vec.mean()) / (vec.std() + 1e-6)


def _match_digit(patch) -> tuple[str, float]:
    """Best-matching digit for one glyph, scored on SHAPE and WIDTH.

    Shape alone is not enough: scaling every glyph to one canvas makes a 3px
    "1" and a 6px "4" the same picture, which is how "21" started reading as
    "24". Each template therefore carries the glyph's natural width, and a
    candidate is penalised for deviating from it — cheap, and it separates the
    one pair the font makes genuinely ambiguous.
    """
    import numpy as np

    vec = _normalise(patch)
    widths = _template_widths()
    best, score = "?", -1e9
    for digit, tpl in _templates().items():
        shape_score = float(np.dot(vec.ravel(), tpl.ravel()) / vec.size)
        width_gap = abs(patch.shape[1] - widths.get(digit, patch.shape[1]))
        total = shape_score - WIDTH_PENALTY * width_gap
        if total > score:
            best, score = digit, total
    return best, score


def _read_number_strip(strip) -> tuple[str | None, float]:
    """Decode an ink strip into digits, returning (text, mean confidence).

    Digit widths vary ("1" is narrow, "0" wide) and neighbouring glyphs
    sometimes touch, so neither fixed-pitch splitting nor ink-gap segmentation
    alone is reliable. A small dynamic program picks the cut points: for every
    position it tries every plausible glyph width and keeps the segmentation
    with the best total template score.
    """

    width = strip.shape[1]
    if width < 2:
        return None, 0.0

    def score_at(start: int, size: int) -> tuple[str, float]:
        # Crop to ink in BOTH axes: a candidate window wider than the glyph
        # would otherwise carry blank columns into the match, which squeezes a
        # narrow "1" to look like a padded "4" and destroys the width feature.
        glyph = _crop_ink(strip[:, start:start + size])
        if glyph is None:
            return "?", -1.0
        return _match_digit(glyph)

    # best[i] = (total score, digit count, text) for the strip from i onward.
    best: list[tuple[float, int, str]] = [(0.0, 0, "")] * (width + 1)
    for i in range(width - 1, -1, -1):
        best[i] = (-1e9, 0, "")
        for size in range(MIN_GLYPH_WIDTH, MAX_GLYPH_WIDTH + 1):
            if i + size > width:
                continue
            # The tail must itself be decodable (or be the end of the strip).
            tail = best[i + size]
            if tail[0] <= -1e8:
                continue
            digit, score = score_at(i, size)
            if score < 0:
                continue
            total = (score - DIGIT_COST) + tail[0]
            if total > best[i][0]:
                best[i] = (total, tail[1] + 1, digit + tail[2])

    total, count, text = best[0]
    if count == 0 or total <= -1e8:
        return None, 0.0
    return text, total / count + DIGIT_COST


def _read_number(patch, min_score: float = MIN_DIGIT_SCORE) -> tuple[int | None, float]:
    """Decode a numeric cell. Returns (value, confidence)."""
    value = _inkness(patch)
    if value is None:
        return None, 1.0
    strip = _crop_ink(value)
    if strip is None:
        return None, 1.0
    text, score = _read_number_strip(strip)
    if text is None or score < min_score or not text.isdigit():
        return None, max(score, 0.0)
    return int(text), score


def _read_date(patch) -> str | None:
    """The DPM header's summary cell holds the sheet date (YYYY-MM-DD)."""
    import numpy as np

    value = _inkness(patch)
    if value is None:
        return None
    mask = value > INK_THRESHOLD
    cols = np.where(mask.any(axis=0))[0]
    if not len(cols):
        return None
    # Split on the separator gaps the hyphens create, then read each group.
    groups, run = [], [cols[0]]
    for prev, cur in zip(cols, cols[1:]):
        if cur - prev > 2:
            groups.append(run)
            run = []
        run.append(cur)
    groups.append(run)
    if len(groups) != 3:
        return None
    parts = []
    for run in groups:
        sub = value[:, run[0]:run[-1] + 1]
        rows = np.where((sub > INK_THRESHOLD).any(axis=1))[0]
        if not len(rows):
            return None
        text, score = _read_number_strip(sub[rows[0]:rows[-1] + 1])
        if text is None or not text.isdigit() or score < MIN_DIGIT_SCORE:
            return None
        parts.append(int(text))
    year, month, day = parts
    if not (2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"



# --- top level --------------------------------------------------------------

def read_supastats_image(data: bytes) -> ParsedSheet:
    """Parse screenshot bytes into a ParsedSheet.

    Raises UnsupportedScreenshot if the image is not a supastats sheet at the
    expected zoom level.
    """
    import numpy as np
    from PIL import Image

    try:
        image = Image.open(BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise UnsupportedScreenshot(f"not a readable image: {exc}") from exc

    arr = np.array(image)
    edges, y0, n_rows, left = _detect_geometry(arr)
    n_maps = len(edges) - 1
    warnings: list[str] = []

    # Row roles come from the label cell's fill: player rows are tinted with
    # their team colour, Round rows are grey, headers/blanks are white.
    roles = []
    for row in range(n_rows):
        label = _classify(_modal_rgb(_label_cell(arr, left, y0, row).astype(int)))
        header = any(
            _classify(_modal_rgb(_cell(arr, edges, y0, c, row).astype(int))) in ("RED", "BLUE")
            for c in range(n_maps)
        )
        roles.append("HEADER" if header and label == "WHITE" else label)

    header_rows = [i for i, r in enumerate(roles) if r == "HEADER"]
    if not header_rows:
        raise UnsupportedScreenshot("no block header row found")

    # Winners: the first header row's map cells carry the winning team's colour.
    winners = [
        {"RED": "RED", "BLUE": "BLUE"}.get(
            _classify(_modal_rgb(_cell(arr, edges, y0, c, header_rows[0]).astype(int)))
        )
        for c in range(n_maps)
    ]

    # Best effort only: the header row uses a smaller font than the data cells
    # and mixes hyphens into the glyph run, so the date often will not decode.
    # The caller resolves the session from the post date instead and confirms it
    # structurally (map count, round durations), which is the stronger signal
    # anyway — supa posts the morning after, so the date on the sheet and the
    # date of the post are not the same thing either.
    session_date = _read_date(_summary_cell(arr, left, y0, header_rows[0]))

    def read_block(start: int, stop: int) -> list[PlayerRow]:
        rows: list[PlayerRow] = []
        for row in range(start + 1, stop):
            if roles[row] not in ("RED", "BLUE"):
                continue
            values, confs = [], []
            for col in range(n_maps):
                val, conf = _read_number(_cell(arr, edges, y0, col, row))
                values.append(val)
                confs.append(conf)
            total, _ = _read_number(_summary_cell(arr, left, y0, row))
            rows.append(PlayerRow(name=None, team=roles[row], values=values, total=total))
        return rows

    bounds = header_rows + [n_rows]
    blocks = [read_block(bounds[i], bounds[i + 1]) for i in range(len(header_rows))]
    dpm = blocks[0] if blocks else []
    kills = blocks[1] if len(blocks) > 1 else []
    effort_present = len(blocks) > 2

    round1: list[int | None] = []
    round2: list[int | None] = []
    round_rows = [i for i, r in enumerate(roles) if r == "ROUND"]
    for idx, row in enumerate(round_rows[:2]):
        durations = [_read_number(_cell(arr, edges, y0, c, row))[0] for c in range(n_maps)]
        (round1 if idx == 0 else round2).extend(durations)

    sheet = ParsedSheet(
        session_date=session_date,
        map_count=n_maps,
        winners=winners,
        dpm=dpm,
        kills=kills,
        effort_present=effort_present,
        round1_seconds=round1,
        round2_seconds=round2,
        warnings=warnings,
    )
    if kills and not sheet.kills_checksum_ok:
        sheet.warnings.append(
            "kills do not sum to the sheet's own totals — digits were misread"
        )
    return sheet
