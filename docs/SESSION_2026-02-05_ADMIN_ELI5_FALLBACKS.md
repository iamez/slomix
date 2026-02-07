# Admin Atlas ELI5 Fallbacks Expansion
Date: 2026-02-05

## Summary
Expanded the automatic fallback descriptions used by the Admin Atlas so script/tool/diagnostic nodes get clearer ELI5 guidance without needing per-node manual text.

## Changes
- Added role detection for `script_*`, `tool_*`, and `diag_*` nodes.
- Added richer ELI5/summary/why/how fields for these roles.
- Improves onboarding clarity for maintenance scripts and diagnostic tools that lack explicit NODE_DETAILS entries.

## Files Touched
- `website/js/admin-panel.js`
