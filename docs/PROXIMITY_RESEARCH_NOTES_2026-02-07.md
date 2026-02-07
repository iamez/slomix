# Proximity Research Notes (2026-02-07)

This is a structured summary of the external research text you provided. The sources referenced there were not verified here, so treat the claims as **informed hypotheses** until we validate them against actual ET:Legacy data.

## Core takeaways worth adopting

### Trades (opportunity → attempt → success)
- **Trade window**: 3–5 seconds is standard in FPS analytics.
- **Opportunity gating**: only count if teammate was in realistic trade range.
- **Attempt**: damage on killer inside the window.
- **Success**: killer dies inside the window.
- **False positive mitigation**: do not count trades that are not in the same skirmish (distance and timing gates).

### Team proximity / cohesion
- **High trade involvement** is a strong proxy for “pack play.”
- **Low trade involvement** can mean a lurker or an entry fragger (not always bad).
- **Distance + clustering** improves accuracy vs time-only trade logic.

### Baiting (negative signal)
- Do **not** score penalties unless confidence is high.
- Use **missed trade candidates** as review data first.
- Guard against false penalties for lurk/objective roles.

### Support positioning
- Support tends to be:
  - high trade participation
  - strong utility impacts
  - low entry attempts
- In ET:Legacy we approximate via proximity + trade metrics since we lack grenade/flash metrics.

### Crossfires
- Two angles covering the same target lane.
- Detection should use a **geometry + timing** check, not only “two attackers hit within window.”
- A practical v1 proxy: two teammates within crossfire radius and sufficiently different view angles.

---

## Mapping to our implementation

### Already implemented (v1)
- Trade window = 3s default (`PROXIMITY_TRADE_WINDOW_MS=3000`)
- Trade opportunities by distance (`PROXIMITY_TRADE_DIST=800`)
- Trade attempts = damage on killer inside window
- Trade success = killer death inside window
- Missed trade candidates logged

### Recommended v1 upgrades
1. **Skirmish gating**
   - Add distance gating for attempts/success (must also have been an opportunity).
2. **Confidence tiering**
   - label missed trades as low/med/high
   - only score high by default
3. **Lurk/Objective exception gates**
   - suppress missed-trade penalties when in objective zone or role context

### V2+ roadmap (from research)
- Use clustering to separate concurrent fights (avoid cross-map “trade” false positives)
- Add crossfire geometry (view angle delta + position)
- Add map control / occupancy heatmaps per team

---

## Practical config suggestions (baseline)
```
trade_window_s: 3.0 (tune 3–5)
trade_dist: 800
support_dist: 600
combat_recent_s: 1.5
isolation_dist: 1200
crossfire_dist: 700
crossfire_min_angle_deg: 40
```

---

## Status
This note is **reference-only** and does not change system behavior. It exists to guide tuning and future work.
