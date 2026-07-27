"""Deterministic, content-verified index of BSP files inside ET PK3 archives."""

from __future__ import annotations

import hashlib
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal

from website.backend.map_geometry.bsp import BspFile, parse_bsp

_HASH_CHUNK_SIZE = 1024 * 1024


class Pk3IndexError(RuntimeError):
    """A PK3 inventory cannot be built or trusted."""


class Pk3BspConflictError(Pk3IndexError):
    """Several providers claim one map name but contain different BSPs."""


class BspContentChangedError(Pk3IndexError):
    """A selected BSP no longer matches the hash recorded during indexing."""


@dataclass(frozen=True, slots=True)
class BspProvider:
    map_name: str
    pk3_path: Path
    bsp_member: str
    member_index: int
    size: int
    crc32: int
    sha256: str

    @property
    def source(self) -> str:
        return f"{self.pk3_path}!/{self.bsp_member}"


@dataclass(frozen=True, slots=True)
class GeometryResolution:
    map_name: str
    status: Literal["geometry", "no_geometry"]
    selected: BspProvider | None
    providers: tuple[BspProvider, ...]
    reason: str | None = None


def _normalise_map_name(value: str) -> str:
    name = value.strip().casefold()
    if name.endswith(".bsp"):
        name = name[:-4]
    if not name or "/" in name or "\\" in name:
        raise ValueError(f"invalid ET map name: {value!r}")
    return name


def _bsp_map_name(member: str) -> str | None:
    normalised = member.replace("\\", "/")
    path = PurePosixPath(normalised)
    if len(path.parts) != 2 or path.parts[0].casefold() != "maps" or path.suffix.casefold() != ".bsp":
        return None
    return _normalise_map_name(path.stem)


def _hash_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _provider_key(provider: BspProvider) -> tuple[str, str, int]:
    return (str(provider.pk3_path).casefold(), provider.bsp_member.casefold(), provider.member_index)


class Pk3GeometryIndex:
    """Immutable index of all direct ``maps/*.bsp`` members in an etmain tree."""

    def __init__(self, etmain_dir: Path, providers: Mapping[str, tuple[BspProvider, ...]]) -> None:
        self.etmain_dir = etmain_dir
        self._providers = MappingProxyType(dict(providers))

    @classmethod
    def scan(cls, etmain_dir: str | Path) -> Pk3GeometryIndex:
        root = Path(etmain_dir).expanduser().resolve()
        if not root.is_dir():
            raise Pk3IndexError(f"etmain directory does not exist: {root}")

        archives = sorted(
            (path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() == ".pk3"),
            key=lambda path: str(path.relative_to(root)).casefold(),
        )
        discovered: dict[str, list[BspProvider]] = defaultdict(list)

        for pk3_path in archives:
            try:
                with zipfile.ZipFile(pk3_path) as archive:
                    for member_index, info in enumerate(archive.infolist()):
                        if info.is_dir():
                            continue
                        map_name = _bsp_map_name(info.filename)
                        if map_name is None:
                            continue
                        discovered[map_name].append(
                            BspProvider(
                                map_name=map_name,
                                pk3_path=pk3_path,
                                bsp_member=info.filename,
                                member_index=member_index,
                                size=info.file_size,
                                crc32=info.CRC,
                                sha256=_hash_member(archive, info),
                            )
                        )
            except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                raise Pk3IndexError(f"cannot index PK3 archive {pk3_path}: {exc}") from exc

        providers: dict[str, tuple[BspProvider, ...]] = {}
        for map_name, candidates in sorted(discovered.items()):
            ordered = tuple(sorted(candidates, key=_provider_key))
            hashes = {provider.sha256 for provider in ordered}
            if len(hashes) != 1:
                detail = ", ".join(f"{provider.pk3_path.name}:{provider.sha256}" for provider in ordered)
                raise Pk3BspConflictError(f"map {map_name!r} has non-identical BSP providers: {detail}")
            providers[map_name] = ordered

        return cls(root, providers)

    @property
    def map_names(self) -> tuple[str, ...]:
        return tuple(self._providers)

    def providers_for(self, map_name: str) -> tuple[BspProvider, ...]:
        return self._providers.get(_normalise_map_name(map_name), ())

    def resolve(self, map_name: str) -> GeometryResolution:
        normalised = _normalise_map_name(map_name)
        providers = self._providers.get(normalised, ())
        if not providers:
            return GeometryResolution(
                map_name=normalised,
                status="no_geometry",
                selected=None,
                providers=(),
                reason="no maps/*.bsp provider found in the indexed etmain tree",
            )
        return GeometryResolution(
            map_name=normalised,
            status="geometry",
            selected=providers[0],
            providers=providers,
        )

    def resolve_many(self, map_names: Iterable[str]) -> tuple[GeometryResolution, ...]:
        names = sorted({_normalise_map_name(map_name) for map_name in map_names})
        return tuple(self.resolve(name) for name in names)

    def read_provider(self, provider: BspProvider) -> bytes:
        try:
            with zipfile.ZipFile(provider.pk3_path) as archive:
                infos = archive.infolist()
                if provider.member_index >= len(infos):
                    raise BspContentChangedError(f"PK3 member index changed for {provider.source}")
                info = infos[provider.member_index]
                if (
                    info.filename != provider.bsp_member
                    or info.file_size != provider.size
                    or provider.crc32 != info.CRC
                ):
                    raise BspContentChangedError(f"PK3 member metadata changed for {provider.source}")
                with archive.open(info, "r") as handle:
                    raw = handle.read()
        except BspContentChangedError:
            raise
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise Pk3IndexError(f"cannot read indexed BSP {provider.source}: {exc}") from exc

        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != provider.sha256:
            raise BspContentChangedError(
                f"BSP content changed for {provider.source}: indexed {provider.sha256}, read {actual_hash}"
            )
        return raw

    def load_bsp(self, map_name: str) -> BspFile:
        resolution = self.resolve(map_name)
        if resolution.selected is None:
            raise Pk3IndexError(f"map {resolution.map_name!r} has no BSP geometry")
        return parse_bsp(self.read_provider(resolution.selected), source=resolution.selected.source)

    def manifest(self, map_names: Iterable[str] | None = None) -> dict:
        resolutions = self.resolve_many(map_names if map_names is not None else self.map_names)
        maps: dict[str, dict] = {}
        for resolution in resolutions:
            selected = resolution.selected
            maps[resolution.map_name] = {
                "status": resolution.status,
                "reason": resolution.reason,
                "selected": _provider_manifest(selected, self.etmain_dir) if selected else None,
                "providers": [_provider_manifest(provider, self.etmain_dir) for provider in resolution.providers],
            }
        missing = [name for name, item in maps.items() if item["status"] == "no_geometry"]
        return {
            "etmain_dir": str(self.etmain_dir),
            "maps": maps,
            "summary": {
                "requested_maps": len(maps),
                "with_geometry": len(maps) - len(missing),
                "without_geometry": len(missing),
                "missing_maps": missing,
            },
        }


def _provider_manifest(provider: BspProvider, root: Path) -> dict:
    try:
        pk3 = str(provider.pk3_path.relative_to(root))
    except ValueError:
        pk3 = str(provider.pk3_path)
    return {
        "pk3": pk3,
        "bsp": provider.bsp_member,
        "size": provider.size,
        "sha256": provider.sha256,
    }
