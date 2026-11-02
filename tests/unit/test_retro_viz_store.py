"""External gallery listing and byte serving share one narrow public root."""
import httpx
import pytest
from fastapi import FastAPI
from starlette.exceptions import HTTPException

from website.backend.services import retro_viz_store as store


@pytest.fixture
def gallery(tmp_path):
    directory = tmp_path / "gallery"
    directory.mkdir()
    return store.RetroVizGallery(directory, required=True)


@pytest.mark.parametrize("damage", ["empty", "relative", "missing", "inside", "symlink", "file"])
def test_explicit_root_refuses_unsafe_paths(tmp_path, monkeypatch, damage):
    root = tmp_path / "code"
    root.mkdir()
    external = tmp_path / "public"
    external.mkdir()
    selected = str(external)
    if damage == "empty":
        selected = ""
    elif damage == "relative":
        selected = "public"
    elif damage == "missing":
        selected = str(tmp_path / "absent")
    elif damage == "inside":
        selected = str(root)
    elif damage == "symlink":
        link = tmp_path / "link"
        link.symlink_to(external)
        selected = str(link)
    elif damage == "file":
        path = tmp_path / "file"
        path.write_text("not a directory")
        selected = str(path)
    monkeypatch.setenv("RETRO_VIZ_ROOT", selected)
    with pytest.raises(ValueError, match="canonical external"):
        store.configured_root(root)


def test_release_requires_explicit_root_but_legacy_retains_default(tmp_path, monkeypatch):
    monkeypatch.delenv("RETRO_VIZ_ROOT", raising=False)
    assert store.configured_root(tmp_path) == (tmp_path / "website/data/retro-viz", False)
    (tmp_path / ".slomix-release.json").write_text("{}")
    with pytest.raises(ValueError, match="requires explicit"):
        store.configured_root(tmp_path)


def test_external_root_accepts_canonical_existing_directory(gallery, monkeypatch):
    monkeypatch.setenv("RETRO_VIZ_ROOT", str(gallery.root))
    assert store.configured_root() == (gallery.root, True)


@pytest.mark.asyncio
async def test_listing_urls_serve_exact_bytes_and_exclude_private_paths(gallery, tmp_path, monkeypatch):
    from website.backend.routers import records_trends

    name = "čar #1%.PNG"
    payload = b"\x89PNG\r\n\x1a\nsynthetic-image"
    (gallery.root / name).write_bytes(payload)
    (gallery.root / ".private.png").write_bytes(b"private")
    (gallery.root / "credentials.env").write_bytes(b"private")
    (gallery.root / "subdirectory").mkdir()
    (gallery.root / "subdirectory/image.png").write_bytes(payload)
    sibling = tmp_path / "gallery-private"
    sibling.mkdir()
    (sibling / "secret.png").write_bytes(b"private")
    (gallery.root / "escape.png").symlink_to(sibling / "secret.png")
    (gallery.root / "internal.png").symlink_to(gallery.root / name)
    monkeypatch.setattr(records_trends, "gallery", gallery)
    app = FastAPI()
    app.add_api_route("/api/retro-viz/gallery", records_trends.get_retro_viz_gallery)
    app.mount("/data/retro-viz", gallery)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/retro-viz/gallery")
        assert response.status_code == 200
        images = response.json()["images"]
        assert len(images) == 1
        assert images[0]["filename"] == name and images[0]["size"] == len(payload)
        response = await client.get(images[0]["url"])
        assert response.status_code == 200 and response.content == payload
        assert response.headers["content-type"] == "image/png"
        for path in (".private.png", "credentials.env", "escape.png", "internal.png", "subdirectory/image.png"):
            assert (await client.get("/data/retro-viz/" + path)).status_code == 404
        assert (await client.head(images[0]["url"])).status_code == 200
        assert (await client.post(images[0]["url"])).status_code == 405


@pytest.mark.asyncio
async def test_missing_legacy_root_is_empty_and_image_is_404(tmp_path):
    gallery = store.RetroVizGallery(tmp_path / "missing", required=False)
    assert gallery.images() == []
    app = FastAPI()
    app.mount("/data/retro-viz", gallery)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/data/retro-viz/missing.png")).status_code == 404


def test_explicit_missing_or_unreadable_root_is_not_empty(gallery, monkeypatch):
    gallery.root = gallery.root / "missing"
    with pytest.raises(HTTPException) as error:
        gallery.images()
    assert error.value.status_code == 503
    gallery.root = gallery.root.parent
    def denied(*args):
        raise PermissionError("private operating system detail")
    monkeypatch.setattr(store.os, "scandir", denied)
    with pytest.raises(HTTPException) as error:
        gallery.images()
    assert error.value.status_code == 503
    assert "private operating" not in error.value.detail


@pytest.mark.parametrize("name", ["../a.png", "sub/a.png", "sub\\a.png", ".secret.png", "a.jpg", "a\0.png"])
def test_non_public_filename_is_refused(name):
    assert not store.public_png(name)
