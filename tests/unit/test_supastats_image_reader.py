"""The supastats screenshot reader must be exact or refuse.

Both fixtures are real sheets supa posted. Their numbers were confirmed against
the database on 2026-08-14, so these are ground-truth expectations, not
snapshots of whatever the reader happened to produce. The 8-map sheet was never
used to build the glyph templates — it is the generalisation check.
"""
from pathlib import Path

import pytest

from bot.services.supastats_image_reader import (
    UnsupportedScreenshot,
    read_supastats_image,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "supastats"
SHEET_7 = FIXTURES / "sheet_7maps_rounds_2026-08-11.png"   # session 144
SHEET_8 = FIXTURES / "sheet_8maps_2026-08-04.png"          # session 143

# Verified against the database (per-map kills, in the sheet's row order).
KILLS_7 = [
    [21, 10, 44, 11, 18, 14, 3],
    [18, 7, 29, 12, 12, 12, 2],
    [9, 5, 15, 7, 9, 6, 3],
    [9, 13, 21, 9, 21, 8, 1],
    [13, 12, 25, 6, 13, 14, 1],
    [8, 16, 17, 7, 12, 11, 3],
]
TOTALS_7 = [121, 92, 54, 82, 84, 74]
WINNERS_7 = ["RED", "BLUE", "RED", "RED", "RED", "BLUE", "RED"]
R1_7 = [340, 388, 720, 179, 297, 329, 93]
R2_7 = [229, 145, 392, 179, 265, 177, 52]

TOTALS_8 = [170, 147, 92, 184, 125, 159]
WINNERS_8 = ["RED", "RED", "BLUE", "BLUE", "BLUE", "RED", "BLUE", "RED"]


def _read(path: Path):
    return read_supastats_image(path.read_bytes())


def test_seven_map_sheet_reads_exactly():
    sheet = _read(SHEET_7)
    assert sheet.map_count == 7
    assert sheet.winners == WINNERS_7
    assert [row.values for row in sheet.kills] == KILLS_7
    assert [row.total for row in sheet.kills] == TOTALS_7


def test_round_durations_read_exactly():
    """The Round 1/2 rows are the cheapest cross-check we have: they are whole
    seconds and must equal our own actual_time to the second."""
    sheet = _read(SHEET_7)
    assert sheet.round1_seconds == R1_7
    assert sheet.round2_seconds == R2_7


def test_eight_map_sheet_generalises():
    """Never used to build the templates — if the reader only memorised its
    training sheet, this is where it shows."""
    sheet = _read(SHEET_8)
    assert sheet.map_count == 8
    assert sheet.winners == WINNERS_8
    assert [row.total for row in sheet.kills] == TOTALS_8
    assert sheet.kills_checksum_ok


def test_kills_checksum_guards_both_sheets():
    """Per-map kills summing to the sheet's own totals is the reader's safety
    net: it is arithmetic the reader did not produce, so it catches a misread
    digit before any comparison is attempted."""
    for path in (SHEET_7, SHEET_8):
        assert _read(path).kills_checksum_ok, path.name


def test_rejects_a_non_sheet_image():
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (200, 120), (255, 255, 255)).save(buffer, format="PNG")
    with pytest.raises(UnsupportedScreenshot):
        read_supastats_image(buffer.getvalue())


def test_rejects_a_different_zoom_level():
    """A sheet pasted at another zoom breaks the 60x17 grid. It must fail
    loudly — silently reading a stretched grid would invent numbers."""
    from io import BytesIO

    from PIL import Image

    image = Image.open(SHEET_7)
    scaled = image.resize((int(image.width * 1.5), int(image.height * 1.5)), Image.LANCZOS)
    buffer = BytesIO()
    scaled.save(buffer, format="PNG")
    with pytest.raises(UnsupportedScreenshot):
        read_supastats_image(buffer.getvalue())


def test_rejects_garbage_bytes():
    with pytest.raises(UnsupportedScreenshot):
        read_supastats_image(b"not an image at all")
