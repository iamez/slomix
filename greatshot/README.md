# Greatshot - Demo Analysis Pipeline

ET:Legacy demo file analysis, highlight detection, and clip extraction pipeline.

**Part of the [Slomix](../README.md) platform. Integrated into the [website](../website/README.md) backend.**

---

## What It Does

Greatshot processes `.dm_84` demo files from ET:Legacy and extracts interesting moments:

1. **Scan** - Parse demo files into normalized event streams (kills, deaths, weapons, timing)
2. **Detect** - Find highlight-worthy sequences (multi-kills, sprees, headshot chains)
3. **Cut** - Extract demo clips around detected highlights (backend wired, cutter TODO)
4. **Render** - Convert clips to video (stub - future phase)

---

## Architecture

```
Upload .dm_84  ──►  Scanner  ──►  Highlight Detector  ──►  Artifacts
                   (parse)        (multi-kill, spree)       (analysis.json, report.txt)
                                                               │
                                                               ▼
                                                        Website UI
                                                     (greatshot.js views)
```

### Pipeline Stages

| Stage | Module | Status |
|-------|--------|--------|
| **Scanner** | `scanner/` | Production - parses `.dm_84` files with timeout + size limits |
| **Highlights** | `highlights/` | Production - multi-kill, spree, headshot chain detection |
| **Contracts** | `contracts/` | Production - schema types, profiles, ET:Legacy weapon mapping |
| **Worker** | `worker/` | Production - safe job runner (`run_analysis_job`) |
| **Cutter** | `cutter/` | API defined, backend wiring TODO |
| **Renderer** | `renderer/` | Stub - dependency checks work, capture/transcode TODO |

---

## Project Structure

```
greatshot/
├── config.py                       # Configuration (env vars, paths, limits)
├── scanner/
│   ├── etl_demo_scan               # CLI tool for standalone scanning
│   ├── adapters.py                 # Parser adapters for different formats
│   └── normalization.py            # Event normalization to internal schema
├── highlights/
│   └── detectors.py                # Highlight detection (multi-kills, sprees, headshot chains)
├── cutter/
│   └── api.py                      # Demo clip extraction wrapper (backend TODO)
├── renderer/
│   └── api.py                      # Render pipeline interface (stub)
├── worker/
│   └── runner.py                   # Safe worker wrapper for analysis jobs
├── contracts/
│   ├── types.py                    # Schema + shared output types
│   ├── schema/
│   │   └── analysis.schema.json    # JSON schema for analysis output
│   └── profiles/
│       ├── profile_detector.py     # Config/metadata-based game detection
│       └── etlegacy_main.py        # ET:Legacy weapon/team mapping
├── tests/
│   ├── test_highlights.py          # Highlight detector unit tests
│   └── fixtures/                   # Golden test data
└── README.md                       # This file
```

---

## Usage

### Scanner CLI

```bash
# Scan a demo file
./greatshot/scanner/etl_demo_scan /path/to/demo.dm_84

# Output to specific files
./greatshot/scanner/etl_demo_scan /path/to/demo.dm_84 \
  --json-out /tmp/analysis.json \
  --txt-out /tmp/report.txt
```

### As Part of Website

Demos are uploaded through the website UI. The backend calls `run_analysis_job()` which:

1. Validates the upload (size, extension, format)
2. Runs the scanner with timeout protection
3. Detects highlights from normalized events
4. Stores artifacts (analysis JSON + text report)
5. Cross-references players with bot database for enrichment

---

## Artifacts

Per uploaded demo, the system stores:

```
{GREATSHOT_STORAGE_ROOT}/{demo_id}/
├── original/original.dm_84         # Original upload
├── artifacts/
│   ├── analysis.json               # Structured analysis output
│   └── report.txt                  # Human-readable report
├── clips/*.dm_84                   # Extracted clips (when cutting enabled)
└── videos/*.mp4                    # Rendered videos (when rendering enabled)
```

---

## Configuration

| Environment Variable | Default | Purpose |
|---------------------|---------|---------|
| `GREATSHOT_STORAGE_ROOT` | `data/greatshot` | Artifact storage path |
| `GREATSHOT_MAX_UPLOAD_BYTES` | - | Max upload file size |
| `GREATSHOT_ALLOWED_EXTENSIONS` | `.dm_84` | Allowed demo formats |
| `GREATSHOT_SCANNER_TIMEOUT_SECONDS` | - | Scanner process timeout |
| `GREATSHOT_SCANNER_MAX_OUTPUT_BYTES` | - | Max parser output size |
| `GREATSHOT_SCANNER_MAX_EVENTS` | - | Max normalized event count |
| `GREATSHOT_UDT_JSON_BIN` | - | UDT JSON parser binary path |
| `GREATSHOT_UDT_CUTTER_BIN` | - | UDT cutter binary path |
| `GREATSHOT_ETLEGACY_CLIENT_PATH` | - | ET:Legacy client for rendering |
| `GREATSHOT_FFMPEG_PATH` | - | FFmpeg for video encoding |

---

## Supported Formats

Current allowlist:

- `.dm_84` (ET:Legacy demos)

Extension points for future formats are separated by profile/adapter:
- Parser adapters in `scanner/adapters.py`
- Game profiles in `contracts/profiles/`

---

## Planned Feature: Demo Cut Tool

A user-facing demo cutting tool is planned:

- Upload a demo file, specify a time range (start/end)
- Server-side cut extracts the specified segment
- Download the trimmed `.dm_84` clip
- Future: "Render" button for video conversion (offline pipeline, not yet implemented)

See [Feature Roadmap](../docs/FEATURE_ROADMAP_2026.md) for details.

---

## Known Limitations

- Cutter backend command syntax not yet wired for ET:Legacy
- Renderer is a stub (dependency checks work, capture/transcode TODO)
- Objective/revive rich event extraction staged for later pass
- Golden fixture suite needs expansion from real uploaded demos

## Tests

```bash
pytest greatshot/tests/ -v
```
