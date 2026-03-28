# Tools

This directory is the home for reusable helper scripts and maintenance utilities.

## Usage Rules

- Keep reusable scripts here instead of the repo root.
- Put one-off or historical utilities in `tools/archive/`.
- Treat scripts that assume local credentials, paths, or old schemas as archival until reviewed.

## Live Entry Points

- [check_production_health.py](/home/samba/share/slomix_discord/tools/check_production_health.py)
  Operator health check for the current platform layout.
- [verify_pipeline.py](/home/samba/share/slomix_discord/tools/verify_pipeline.py)
  Pipeline verification helper.
- [pipeline_health_report.py](/home/samba/share/slomix_discord/tools/pipeline_health_report.py)
  Pipeline inspection/reporting helper.
- [tools/windows](/home/samba/share/slomix_discord/tools/windows)
  Windows-specific local helper scripts that are still referenced by active docs.

## Archive

- [tools/archive](/home/samba/share/slomix_discord/tools/archive)
  Older helpers that are retained for reference.
- [tools/archive/root_diagnostics](/home/samba/share/slomix_discord/tools/archive/root_diagnostics)
  Root-level diagnostic scripts moved during cleanup because they are not part of normal runtime or current operator workflows.
