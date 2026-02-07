# Proximity Map Overlay Plan (2026-02-07)

## Goal
Render proximity paths (engagements + movement) on actual map images so the spatial data is readable at a glance.

## Why this matters
The proximity system is about team chemistry and positioning. Without a map overlay, path lines are abstract and hard to interpret. The overlay is the “aha” visualization for new users and for validating data quality.

---

## Two implementation options

### Option A — Fast overlay (approximate)
**What it is:**
- Use existing map art (e.g., `website/assets/maps/*.svg`) as background.
- Apply a rough transform to X/Y to fit the image.

**Pros:**
- Fast to ship.
- Good for storytelling and demoing the pipeline.

**Cons:**
- Not accurate: coordinate alignment will drift.
- Harder to trust for “true” spatial validation.


### Option B — Accurate overlay (calibrated) (recommended)
**What it is:**
- Use real top‑down map images (minimap screenshots or extracted assets).
- Add a calibration tool where you click points on the image and enter their world X/Y.
- Compute affine transform (or 2‑point scale + offset) to map world coords → pixel coords.
- Store calibration per map in DB or JSON.

**Pros:**
- Accurate and defensible.
- Enables future features (objective zones, choke analysis, role detection).

**Cons:**
- Requires map images + reference points.
- Slightly more work upfront.

---

## Required assets and data

### Map images
- Top‑down minimap for each active map.
- Standard size per map preferred (consistent scaling).
- File format: PNG or SVG.

### Calibration points
- For each map, identify 2–3 known world coordinates.
- Use landmarks (spawn, objective, notable props).
- Stored as:
  ```json
  {
    "map_name": "etl_adlernest",
    "image": "assets/maps/etl_adlernest_top.png",
    "points": [
      {"pixel": [120, 330], "world": [1234, 5678]},
      {"pixel": [820, 90],  "world": [4321, 2100]}
    ]
  }
  ```

---

## Technical plan (Option B)

### 1) Data model
Add a calibration table or JSON file:
- Table: `map_calibration`
- Fields:
  - `map_name`
  - `image_path`
  - `pixel_points` (JSON)
  - `world_points` (JSON)
  - `created_at`, `updated_at`

### 2) Calibration UI
- New admin tool:
  - Show map image
  - Click to add pixel points
  - Input world X/Y for each point
  - Save calibration

### 3) Transform math
- Compute transform from world → pixel.
- Start with simple scale + offset.
- Upgrade to affine transform if needed.

### 4) Rendering
- In `proximity.js`, project path points into pixel space.
- Draw on canvas over the map image.
- Keep path event markers (hit/death/escape).

### 5) Testing
- Compare paths against known positions.
- Validate crossfire clusters and hotzones appear where expected.

---

## Integration locations

- API: `website/backend/routers/api.py`
  - Add `/proximity/map/{map_name}` to return calibration + image path
- Frontend: `website/js/proximity.js`
  - Load calibration
  - Use it to convert path points
- Assets: `website/assets/maps/`
- DB (optional): migrations for `map_calibration`

---

## Risks / unknowns

- Map asset availability (need top‑down images).
- Coordinate mismatch if map uses different origin/scale.
- Need consistent axis orientation (ET uses Quake 3 coords).

---

## Next steps (when we resume)

1. Decide Option A vs B.
2. Collect or generate top‑down images for 5–10 key maps.
3. Choose 2–3 reference coordinates per map.
4. Implement calibration storage + tool.
5. Wire overlay into proximity inspector + heatmap.

