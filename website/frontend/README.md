# Slomix Modern Frontend Workspace

This workspace is the first migration seam for the website tech-stack upgrade.

Rules:

- `website/index.html` stays the only top-level HTML entry for the production site.
- `website/js/app.js` stays the top-level hash router and rollback switch.
- Built assets are emitted to `website/static/modern/` and loaded same-origin by the legacy shell.
- Source files under `website/frontend/` are not public and are blocked by FastAPI before `StaticFiles`.

Scripts:

```bash
npm install
npm run typecheck
npm run build
npm run dev
```

Notes:

- `npm run build` writes a fixed runtime bundle to `website/static/modern/route-host.js` plus `route-host.css`.
- `npm run dev` is only for isolated preview work inside this workspace. It does not own the production shell or hash routing.
- A route should only switch from `legacy` to `modern` after parity checks and backend contract gates are green.
