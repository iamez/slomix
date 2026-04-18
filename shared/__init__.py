"""Shared package — re-exports of bot modules used by both bot and website.

The canonical implementations live under `bot/`. This package exists so
website/backend can import them via `shared.X` instead of `bot.X`,
which:
- Documents the explicit cross-boundary surface area
- Makes a future bot ↔ website split a pure rename (no logic moves)
- Keeps grep-noise for 'from bot.' out of website/ to zero

Each module here is a thin re-export. Adding a new shared symbol requires
adding it here AND in the canonical bot/ location.
"""
