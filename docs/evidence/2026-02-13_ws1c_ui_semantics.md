# Evidence: WS1C-005 Proximity UI Semantics Clarification
Date: 2026-02-12  
Workstream: WS1C (Proximity Source Health)  
Task: `WS1C-005`  
Status: `done`

## Goal
Clarify proximity chart semantics in UI so timeline/hotzone cards explicitly communicate:
1. what the visualization encodes,
2. the active scope (session/map/round),
3. operator-readable legend/tooltips.

## Changes Applied
1. Updated `website/index.html`:
   - Added `#proximity-timeline-scope` label above timeline chart.
   - Added timeline legend chips with tooltip text:
     - bucket meaning,
     - bar-height intensity meaning.
   - Added `#proximity-heatmap-scope` label above hotzone map.
   - Added hotzone legend chips with tooltip text:
     - hotzone bin meaning,
     - size/color kill-density meaning.
2. Updated `website/js/proximity.js`:
   - `updateScopeUIText()` now updates:
     - `proximity-timeline-scope`
     - `proximity-heatmap-scope`
     - existing scope caption/window label
   - `renderHeatmap()` caption now includes scope context.
   - `resetProximityValues()` resets new scope labels to default window text.

## Validation
1. Syntax check:
```bash
node --check website/js/proximity.js
```
2. Presence checks:
```bash
rg -n "proximity-timeline-scope|proximity-heatmap-scope|Bucketed engagements|Size/color = kills" website/index.html website/js/proximity.js
```
3. Results:
   - JS syntax check passed.
   - New semantic labels and legend anchors exist in UI markup and are wired in runtime JS updates.

## Decision
1. Timeline/hotzone cards now expose explicit semantic legends.
2. Scope/round-level context is visible directly on each card.
3. `WS1C-005` is closed.
