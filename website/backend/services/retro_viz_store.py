"""One public PNG-only root for gallery listing and serving; never creates state."""
from __future__ import annotations

import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[3]


def configured_root(root: Path = ROOT) -> tuple[Path, bool]:
    selected = os.getenv("RETRO_VIZ_ROOT")
    if selected is None:
        if (root / ".slomix-release.json").exists():
            raise ValueError("Git-free gallery requires explicit RETRO_VIZ_ROOT")
        return root / "website/data/retro-viz", False
    path = Path(selected)
    if (not selected or not path.is_absolute() or not path.is_dir()
            or path.resolve() != path or path.is_relative_to(root.resolve())):
        raise ValueError("RETRO_VIZ_ROOT must be an existing canonical external directory")
    return path, True


def public_png(name: str) -> bool:
    return (bool(name) and not name.startswith(".") and name.lower().endswith(".png")
            and not any(c in name for c in ("/", "\\", "\0")))


class RetroVizGallery(StaticFiles):
    def __init__(self, directory: Path, *, required: bool):
        self.root = directory
        self.required = required
        super().__init__(directory=directory, check_dir=False, follow_symlink=False)

    def available(self) -> bool:
        if not self.root.exists() and not self.required:
            return False  # Preserve legacy optional gallery, not a broken explicit path.
        if not self.root.is_dir() or self.root.resolve() != self.root:
            raise HTTPException(503, "Gallery storage unavailable")
        return True

    async def check_config(self):
        # Optional legacy gallery may appear after startup. Recheck per request.
        self.available()

    def images(self) -> list[dict]:
        try:
            if not self.available():
                return []
            images = []
            with os.scandir(self.root) as entries:
                for entry in sorted(entries, key=lambda item: item.name):
                    if not public_png(entry.name):
                        continue
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        continue  # A concurrently removed image is no longer listed.
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    images.append({
                        "filename": entry.name,
                        "url": "/data/retro-viz/" + quote(entry.name, safe=""),
                        "size": info.st_size,
                        "modified": datetime.fromtimestamp(info.st_mtime, tz=timezone.utc).isoformat(),
                    })
            return images
        except OSError:
            raise HTTPException(503, "Gallery storage unavailable") from None

    async def get_response(self, path, scope):
        if not public_png(path) or not self.available() or (self.root / path).is_symlink():
            raise HTTPException(404)
        return await super().get_response(path, scope)


_directory, _required = configured_root()
gallery = RetroVizGallery(directory=_directory, required=_required)
