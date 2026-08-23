"""How wrong Layer 1's positions are, measured — so the page can say so.

Layer 1 places a player at their last position sample at or before `t`. Until
this module existed, a player whose last sample was 70 seconds old was drawn
exactly as confidently as one sampled 100 ms ago, and nothing in the payload let
a reader tell them apart. That was the spider-web prototype's real weakness: not
that it drew too little, but that everything it drew looked equally certain.

MEASURED, NOT ASSUMED

`scripts/validate_layer1_reconstruction.py` compares the reconstruction against
two independently written sources — the attacker position recorded at each
obituary, and the shot origins recorded during ordinary play. The victim
coordinate is excluded because it and the track's death sample are copied from
the same `death_pos` local, so comparing them would measure the writer.

⭐ THE SPLIT ON `overlap_conflict` IS THE POINT. The first run reported a p99 of
2,036 units on samples under 200 ms old, which is impossible — a player covers
about 64 units in that time. Re-checking every life instead of the chosen one
found the cause: of 88 such outliers, 71 would have been correct had a different
life been picked, and 64 were already flagged `overlap_conflict`. Separating
them drops the fresh-band p99 from 2,036 to **67 units**, and gives the disputed
positions an honest error of their own (~900 units median) instead of smearing
it across everyone.

⭐ Both sources agree closely, which is what makes the numbers evidence rather
than one script's opinion: 12.3 vs 8.5 units (clean, fresh) and 899.9 vs 851.4
(conflicted, fresh), from two different writers.

⚠️ These are frozen measurements of a specific corpus on a specific date, not
constants of nature. `MEASUREMENT` carries the provenance so a reader three
months from now can tell whether they still describe the code they are reading.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Provenance for every number below. Published in the API payload so the figure
#: and the conditions it was measured under travel together.
MEASUREMENT = {
    "measured_at": "2026-08-22",
    "script": "scripts/validate_layer1_reconstruction.py",
    "rounds": 150,
    "samples": {"attacker": 7869, "shot": 57929},
    "sources": ("proximity_combat_position.attacker_*", "proximity_shot_fired.origin_*"),
    "unit": "game units (a player is about 40 wide)",
    "excluded": "victim coordinate (shares a writer with the track's death sample)",
}


@dataclass(frozen=True, slots=True)
class PositionError:
    """Expected distance between the drawn position and the real one."""

    p50: float
    p90: float
    #: False when the band rests on too few samples to state a p90 honestly.
    well_sampled: bool
    #: Why this row applies — goes into the payload beside the numbers.
    basis: str


#: (upper bound of sample age in ms, error when the life is clean).
#: The last entry is open-ended: a stale sample has no natural ceiling, and a
#: player who disconnects mid-round can leave one arbitrarily old.
#:
#: ⚠️ The 200–5000 ms bands rest on 9–645 samples each and their percentiles
#: swing accordingly (the 200–500 band gives 125 units from one source and 1,137
#: from the other, on n=15 and n=9). They are marked not-well-sampled rather
#: than dropped, because a reader needs to know the drawing is uncertain there
#: even when we cannot say precisely how uncertain.
CLEAN_BANDS: tuple[tuple[int | None, float, float, bool], ...] = (
    (200, 12.0, 44.0, True),        # n=59,368 across both sources
    (500, 125.0, 1017.0, False),    # n=24
    (1000, 46.0, 1479.0, False),    # n=31
    (2000, 13.0, 688.0, False),     # n=164
    (5000, 38.0, 347.0, False),     # n=711
    (None, 530.0, 1700.0, True),    # n=4,479
)

#: Same, for a life Layer 1 has flagged `overlap_conflict`. Only the fresh band
#: carries enough samples to state; beyond it the flag alone is the warning.
CONFLICT_BANDS: tuple[tuple[int | None, float, float, bool], ...] = (
    (200, 875.0, 2500.0, True),     # n=1,021 across both sources
    (None, 875.0, 2500.0, False),
)


#: How far a player actually gets in N seconds, measured. Upper edge of each
#: band in ms, then the p99 displacement in game units.
#:
#: ⭐ DISPLACEMENT, NOT SPEED x TIME. The obvious model multiplies a speed
#: percentile by the age, and it overstates by 50-80%: the stored `speed`
#: samples put p99 at 533 units/s over 703,000 samples, which across eight
#: seconds would be 4,266 units, while the players themselves cover 2,371.
#: Nobody holds top speed in a straight line for eight seconds — they turn,
#: stop, fight and die. The naive figure describes a player who does not exist.
#:
#: ⭐ p99, because this sizes a CONTAINMENT claim. The region has to hold the
#: true position, so it is sized by the tail; a median would be wrong about
#: precisely the players who moved.
REACH_BANDS: tuple[tuple[int | None, float], ...] = (
    (1000, 353.0),     # n=306,755
    (2000, 736.0),     # n=369,235
    (3000, 1106.0),    # n=354,151
    (4000, 1434.0),    # n=339,098
    (5000, 1717.0),    # n=324,124
    (6000, 1956.0),    # n=309,299
    (7000, 2170.0),    # n=294,650
    (8000, 2371.0),    # n=280,302
    (None, 2522.0),    # n=161,322
)

#: Provenance for REACH_BANDS, published beside the numbers for the same reason
#: MEASUREMENT is.
REACH_MEASUREMENT = {
    "measured_at": "2026-08-23",
    "script": "scripts/measure_reach_bound.py",
    "rounds": 60,
    "pairs": 2739236,
    "source": "player_track.path, forward pairs within one life",
    "statistic": "p99 displacement in game units",
    "unit": "game units (a player is about 40 wide)",
    # ⚠️ The second route agrees on shape and converges by 6-8 s, but reads
    # LOWER at short windows (222 vs 353 at 1 s). That is not a disagreement
    # about movement: a shot pair starts at a moment the player was SHOOTING,
    # and someone shooting is standing or strafing rather than crossing the
    # map. Two populations, not two answers. The track bands are kept because
    # they are the unbiased population and the larger radius is the
    # conservative one for a claim that must contain the truth.
    "cross_check": {
        "source": "proximity_shot_fired.origin_*, 60 rounds carrying shots",
        "p99_at_1s": 222.4, "p99_at_4s": 1028.3, "p99_at_8s": 2647.3,
    },
}


def reach_bound(age_ms: int) -> float:
    """How far the subject could have moved since the belief was formed.

    Zero for a belief observed at this instant, and never negative: a caller
    asking about a moment before the observation is asking about a belief that
    did not exist yet, and `confidence` already returns 0.0 there.
    """
    if age_ms <= 0:
        return 0.0
    for upper, p99 in REACH_BANDS:
        if upper is None or age_ms < upper:
            return p99
    raise AssertionError("unreachable: the last band is open-ended")


def position_error(stale_ms: int | None, *, overlap_conflict: bool = False) -> PositionError | None:
    """The measured error for one player's drawn position.

    Returns None when there is no position to qualify — a caller with no sample
    has nothing to attach an error bar to, and inventing one would suggest a
    position exists.
    """
    if stale_ms is None or stale_ms < 0:
        return None

    bands = CONFLICT_BANDS if overlap_conflict else CLEAN_BANDS
    for upper, p50, p90, well_sampled in bands:
        if upper is None or stale_ms < upper:
            basis = (
                "overlapping lives: the reconstruction cannot tell which life "
                "this player was on"
                if overlap_conflict
                else f"sample age {stale_ms} ms"
            )
            return PositionError(p50=p50, p90=p90, well_sampled=well_sampled, basis=basis)
    raise AssertionError("unreachable: the last band is open-ended")


def to_dict(error: PositionError | None) -> dict | None:
    if error is None:
        return None
    return {
        "p50": error.p50,
        "p90": error.p90,
        "well_sampled": error.well_sampled,
        "basis": error.basis,
    }
