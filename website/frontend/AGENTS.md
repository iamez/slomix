# AGENTS.md — website/frontend

Two build targets live here. `npm run build` is the **legacy** route host
(`website/js` + `src/pages`, what production serves); the new SPA is
`src/app/` and builds with **`npm run build:app`** into `website/static/app`,
served at `/app` by the FastAPI backend (dev only; production has no SPA).
A green `npm run build` proves nothing about the SPA.

- `src/api/generated/openapi.d.ts` is generated from `docs/api/openapi.json`
  and gitignored; `pretypecheck` / `pretest` / `prebuild:app` regenerate it.
  After a merge, run the npm script, not bare `npx tsc` — a stale file fails
  typecheck on other people's code.
- Design system (docs/design 03/11): hairlines instead of cards, radius 0, no
  gradients or shadows, tokens only (`var(--color-…)`, `var(--space-…)`,
  `var(--fs-…)`); the vocabulary tests (`vocabulary.test`, `tokens.test`) are
  ratchets — a budget that goes up is a regression, not a "known count".
- Three states are separate components: `Absent` (needs a reason, an empty
  array is not a reason), `Unavailable` (request failed), `Pending`.
- Every page section carries `data-parity="<route>.<panel>"`; the parity
  keymap (`docs/parity/keymap.json`, `tests/unit/test_parity_keymap.py`) and
  the endpoint ratchet (`tests/data/endpoint_gap.txt`) are ground truth — a
  line is deleted only with proof (live `/openapi.json` + one real call).
- Fixtures under `pages/__fixtures__/` are recordings from the dev server
  (`scripts/record_api_corpus.py`); the union of shapes matters, one sample
  shows only the branches it triggered. A fixture that carries a real Discord
  snowflake or a private name must not be committed.
- Routes: `src/app/routes.data.json` is the one table (Node reads JSON, not
  TS); `routes.test.ts` checks PAGES ↔ `built`, redirects and sample params;
  `e2e/app-routes.spec.ts` needs `SAMPLES` for every `:param`.
- e2e runs against a live backend (`SMOKE_BASE_URL`); the "owner" project is
  a signed-in non-admin (sentinel id −1), never an admin.
- Never start chromium while another agent's Playwright/audit is running
  (2 GB box). Kill leftovers by PID from `ps`, not `pkill -f`.

## Modularity rules (2026-09-07; measured basis and plan in `docs/SPA_MODULARITY.md`)

- A panel is `<Panel>` (`components/Panel.tsx` once slice 1 lands; `ProxPanel` in
  `pages/proximityShared.tsx` until then). Never hand-roll
  `isPending && <Pending/>` / `isError && <Unavailable/>` / `<Absent/>` again.
- Rows are `<DataTable>` with `DataColumn<Row>[]` declared as data, or `<GridRow>`;
  no new `gridTemplateColumns` in `pages/`.
- Numbers and dates go through `lib/format.ts`; no `.toFixed(` in `pages/`.
- Sizes and colours are tokens (`var(--fs-*)`, `var(--space-*)`, colour tokens);
  no hex/rgb()/raw px except the 1px hairline. "Make it bigger/brighter" is a
  `tokens.css` edit, never a page edit.
- Every section carries `data-parity="page.panel"` and (after slice 6) a
  `dataset_registry.py` descriptor.
- Each rule is a ratchet whose budget only falls, in the same commit that earns it.
- The owner's visual complaints live in `docs/DESIGN_PUNCHLIST.md`; fix them through
  the shared unit so the fix reaches every page.

