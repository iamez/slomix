# Demos Module

This directory contains the ET:Legacy demo pipeline used by the existing `website` backend.

## Layout

- `scanner/`: parser adapters + normalization and CLI (`etl_demo_scan`)
- `highlights/`: clip-worth detector logic (multi-kills, sprees, quick headshot chains)
- `cutter/`: demo clip extraction wrapper (API in place, backend wiring TODO)
- `renderer/`: render pipeline interface + dependency checks (stub in this phase)
- `worker/`: safe worker wrapper (`run_analysis_job`) that writes artifacts
- `contracts/`: schema + shared output types + profile mapping layer
- `tests/`: focused unit tests for highlight detectors and scanner shape

## Supported Formats

Current allowlist starts with:

- `.dm_84` (ET:Legacy demos)

Future extension points are already separated by profile/adapter:

- additional parser adapters in `scanner/adapters.py`
- additional mod profiles in `contracts/profiles/`

## ET vs ET:Legacy

`greatshot-web` ideas are reused, but this module is ET:Legacy-aware:

- profile detection from config/server metadata
- canonical weapon/team mapping layer (`contracts/profiles/`)
- parser output normalized into internal event schema

## Artifacts

Per uploaded demo, backend stores outputs in a private server path (outside web root):

- `original/original.dm_84`
- `artifacts/analysis.json`
- `artifacts/report.txt`
- `clips/*.dm_84` (when cutting enabled)
- `videos/*.mp4` (when rendering enabled)

## Scanner CLI

```bash
./greatshot/scanner/etl_demo_scan /path/to/demo.dm_84
./greatshot/scanner/etl_demo_scan /path/to/demo.dm_84 --json-out /tmp/out.json --txt-out /tmp/out.txt
```

Scanner hardening controls:

- timeout
- max parser output size
- max normalized event count

## Environment Knobs

- `GREATSHOT_STORAGE_ROOT` (default: `data/greatshot`)
- `GREATSHOT_MAX_UPLOAD_BYTES`
- `GREATSHOT_ALLOWED_EXTENSIONS` (default: `.dm_84`)
- `GREATSHOT_SCANNER_TIMEOUT_SECONDS`
- `GREATSHOT_SCANNER_MAX_OUTPUT_BYTES`
- `GREATSHOT_SCANNER_MAX_EVENTS`
- `GREATSHOT_UDT_JSON_BIN`
- `GREATSHOT_UDT_CUTTER_BIN`
- `GREATSHOT_ETLEGACY_CLIENT_PATH`
- `GREATSHOT_FFMPEG_PATH`

## Known Limitations (Current Phase)

- Cutting backend command syntax is not wired yet for ET:Legacy in this deployment.
- Render pipeline is a strict stub: dependency checks work, capture/transcode automation is TODO.
- Objective/revive rich event extraction is staged for a later pass.

## Next Steps

1. Wire a verified ET:Legacy cutter backend in `cutter/api.py`.
2. Implement deterministic capture profile in `renderer/api.py`.
3. Extend scanner normalization with objective/revive/event richness.
4. Add larger golden fixture suite from real uploaded greatshot.
