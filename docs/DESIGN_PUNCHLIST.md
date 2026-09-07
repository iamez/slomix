# Design punch list — what the owner wants changed on the new site

Owner writes rows; an agent fixes each through a token, a `Panel` prop, a
column list or a register descriptor (see `docs/SPA_MODULARITY.md`), never by
editing one page's inline styles, and marks the row with the PR. Keep it short:
one row per complaint, the route, what is wrong, what "fixed" looks like.

Status: `open` → `pr #…` → `done <date>`.

| route (`/app/…`) | panel (`data-parity`) | what is wrong | what fixed looks like | status |
|---|---|---|---|---|
| (example) `/sessions/154` | `session-detail.basics` | numbers too small to read on a laptop | value size = `--fs-value`, label = `--fs-small` | open |
