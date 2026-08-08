"""Content-verified index of map assets inside ET PK3 archives."""

from __future__ import annotations

import hashlib
import lzma
import zipfile
import zlib
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal

from website.backend.map_geometry.bsp import BspFile, parse_bsp

_HASH_CHUNK_SIZE = 1024 * 1024


class Pk3IndexError(RuntimeError):
    """A PK3 inventory cannot be built or trusted."""


class AssetContentChangedError(Pk3IndexError):
    """An indexed map asset no longer matches its recorded content."""


class MapAssetKind(StrEnum):
    """Direct ``maps/`` inputs consumed by the Spider Web toolchain."""

    BSP = "bsp"
    SCRIPT = "script"
    OBJDATA = "objdata"


_ASSET_SUFFIXES = {f".{kind.value}": kind for kind in MapAssetKind}


@dataclass(frozen=True, slots=True)
class MapAssetProvider:
    map_name: str
    asset_kind: MapAssetKind
    pk3_path: Path
    member: str
    member_index: int
    size: int
    crc32: int
    sha256: str

    @property
    def source(self) -> str:
        return f"{self.pk3_path}!/{self.member}"


@dataclass(frozen=True, slots=True)
class MapAssetResolution:
    map_name: str
    asset_kind: MapAssetKind
    status: Literal["resolved", "missing", "ambiguous"]
    selected: MapAssetProvider | None
    providers: tuple[MapAssetProvider, ...]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GeometryResolution:
    map_name: str
    status: Literal["geometry", "no_geometry", "ambiguous_geometry"]
    selected: MapAssetProvider | None
    providers: tuple[MapAssetProvider, ...]
    reason: str | None = None


def _normalise_map_name(value: str) -> str:
    name = value.strip().casefold()
    for suffix in _ASSET_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    if not name or "/" in name or "\\" in name:
        raise ValueError(f"invalid ET map name: {value!r}")
    return name


def _normalise_asset_kind(value: MapAssetKind | str) -> MapAssetKind:
    if isinstance(value, MapAssetKind):
        return value
    try:
        return MapAssetKind(value.strip().casefold().removeprefix("."))
    except ValueError as exc:
        expected = ", ".join(kind.value for kind in MapAssetKind)
        raise ValueError(f"invalid map asset kind {value!r}; expected one of: {expected}") from exc


def _map_asset_identity(member: str) -> tuple[str, MapAssetKind] | None:
    path = PurePosixPath(member.replace("\\", "/"))
    if len(path.parts) != 2 or path.parts[0].casefold() != "maps":
        return None
    asset_kind = _ASSET_SUFFIXES.get(path.suffix.casefold())
    if asset_kind is None:
        return None
    return _normalise_map_name(path.stem), asset_kind


def _hash_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _provider_key(provider: MapAssetProvider) -> tuple[str, str, str, str, int]:
    path = str(provider.pk3_path)
    return (path.casefold(), path, provider.member.casefold(), provider.member, provider.member_index)


class Pk3GeometryIndex:
    """Immutable index of direct BSP, script and objdata map assets.

    Different duplicate contents remain ambiguous. The index has no authority
    to infer the live engine's pak precedence from filename or scan order.
    """

    def __init__(
        self,
        etmain_dir: Path,
        providers: Mapping[tuple[str, MapAssetKind], tuple[MapAssetProvider, ...]],
    ) -> None:
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
        discovered: dict[tuple[str, MapAssetKind], list[MapAssetProvider]] = defaultdict(list)

        for pk3_path in archives:
            try:
                with zipfile.ZipFile(pk3_path) as archive:
                    for member_index, info in enumerate(archive.infolist()):
                        if info.is_dir():
                            continue
                        identity = _map_asset_identity(info.filename)
                        if identity is None:
                            continue
                        map_name, asset_kind = identity
                        discovered[(map_name, asset_kind)].append(
                            MapAssetProvider(
                                map_name=map_name,
                                asset_kind=asset_kind,
                                pk3_path=pk3_path,
                                member=info.filename,
                                member_index=member_index,
                                size=info.file_size,
                                crc32=info.CRC,
                                sha256=_hash_member(archive, info),
                            )
                        )
            except (OSError, EOFError, zipfile.BadZipFile, RuntimeError, zlib.error, lzma.LZMAError) as exc:
                raise Pk3IndexError(f"cannot index PK3 archive {pk3_path}: {exc}") from exc

        providers: dict[tuple[str, MapAssetKind], tuple[MapAssetProvider, ...]] = {}
        for identity, candidates in sorted(
            discovered.items(),
            key=lambda item: (item[0][0], item[0][1].value),
        ):
            providers[identity] = tuple(sorted(candidates, key=_provider_key))

        return cls(root, providers)

    @property
    def map_names(self) -> tuple[str, ...]:
        """Map names with a BSP provider, retained as the W2 default set."""

        return tuple(sorted(map_name for map_name, kind in self._providers if kind is MapAssetKind.BSP))

    @property
    def asset_map_names(self) -> tuple[str, ...]:
        return tuple(sorted({map_name for map_name, _kind in self._providers}))

    def providers_for_asset(
        self,
        map_name: str,
        asset_kind: MapAssetKind | str,
    ) -> tuple[MapAssetProvider, ...]:
        identity = (_normalise_map_name(map_name), _normalise_asset_kind(asset_kind))
        return self._providers.get(identity, ())

    def providers_for(self, map_name: str) -> tuple[MapAssetProvider, ...]:
        """Compatibility wrapper returning BSP providers for one map."""

        return self.providers_for_asset(map_name, MapAssetKind.BSP)

    def resolve_asset(
        self,
        map_name: str,
        asset_kind: MapAssetKind | str,
    ) -> MapAssetResolution:
        normalised = _normalise_map_name(map_name)
        kind = _normalise_asset_kind(asset_kind)
        providers = self._providers.get((normalised, kind), ())
        if not providers:
            return MapAssetResolution(
                map_name=normalised,
                asset_kind=kind,
                status="missing",
                selected=None,
                providers=(),
                reason=f"no maps/<map>.{kind.value} provider found in the indexed etmain tree",
            )

        hashes = {provider.sha256 for provider in providers}
        if len(hashes) != 1:
            detail = ", ".join(f"{provider.pk3_path.name}:{provider.sha256}" for provider in providers)
            return MapAssetResolution(
                map_name=normalised,
                asset_kind=kind,
                status="ambiguous",
                selected=None,
                providers=providers,
                reason=(f"providers contain different bytes and verified live pak precedence is unavailable: {detail}"),
            )

        return MapAssetResolution(
            map_name=normalised,
            asset_kind=kind,
            status="resolved",
            selected=providers[0],
            providers=providers,
        )

    def resolve(self, map_name: str) -> GeometryResolution:
        asset = self.resolve_asset(map_name, MapAssetKind.BSP)
        status_by_asset = {
            "resolved": "geometry",
            "missing": "no_geometry",
            "ambiguous": "ambiguous_geometry",
        }
        return GeometryResolution(
            map_name=asset.map_name,
            status=status_by_asset[asset.status],
            selected=asset.selected,
            providers=asset.providers,
            reason=asset.reason,
        )

    def resolve_many(self, map_names: Iterable[str]) -> tuple[GeometryResolution, ...]:
        names = sorted({_normalise_map_name(map_name) for map_name in map_names})
        return tuple(self.resolve(name) for name in names)

    def read_provider(self, provider: MapAssetProvider) -> bytes:
        try:
            with zipfile.ZipFile(provider.pk3_path) as archive:
                infos = archive.infolist()
                if provider.member_index >= len(infos):
                    raise AssetContentChangedError(f"PK3 member index changed for {provider.source}")
                info = infos[provider.member_index]
                if info.filename != provider.member or info.file_size != provider.size or provider.crc32 != info.CRC:
                    raise AssetContentChangedError(f"PK3 member metadata changed for {provider.source}")
                with archive.open(info, "r") as handle:
                    raw = handle.read()
        except AssetContentChangedError:
            raise
        except (OSError, EOFError, zipfile.BadZipFile, RuntimeError, zlib.error, lzma.LZMAError) as exc:
            raise Pk3IndexError(f"cannot read indexed asset {provider.source}: {exc}") from exc

        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != provider.sha256:
            raise AssetContentChangedError(
                f"asset content changed for {provider.source}: indexed {provider.sha256}, read {actual_hash}"
            )
        return raw

    def load_bsp(self, map_name: str) -> BspFile:
        resolution = self.resolve(map_name)
        if resolution.selected is None:
            raise Pk3IndexError(f"map {resolution.map_name!r} has no unambiguous BSP geometry: {resolution.reason}")
        return parse_bsp(self.read_provider(resolution.selected), source=resolution.selected.source)

    def manifest(self, map_names: Iterable[str] | None = None) -> dict:
        resolutions = self.resolve_many(map_names if map_names is not None else self.map_names)
        maps: dict[str, dict] = {}
        asset_counts = {kind.value: {"resolved": 0, "missing": 0, "ambiguous": 0} for kind in MapAssetKind}

        for resolution in resolutions:
            assets: dict[str, dict] = {}
            for kind in MapAssetKind:
                asset = self.resolve_asset(resolution.map_name, kind)
                asset_counts[kind.value][asset.status] += 1
                assets[kind.value] = _resolution_manifest(asset, self.etmain_dir)

            selected = resolution.selected
            maps[resolution.map_name] = {
                "status": resolution.status,
                "reason": resolution.reason,
                "selected": _provider_manifest(selected, self.etmain_dir) if selected else None,
                "providers": [_provider_manifest(provider, self.etmain_dir) for provider in resolution.providers],
                "assets": assets,
            }

        missing = [name for name, item in maps.items() if item["status"] == "no_geometry"]
        ambiguous = [name for name, item in maps.items() if item["status"] == "ambiguous_geometry"]
        with_geometry = sum(item["status"] == "geometry" for item in maps.values())
        return {
            "etmain_dir": str(self.etmain_dir),
            "maps": maps,
            "summary": {
                "requested_maps": len(maps),
                "with_geometry": with_geometry,
                "without_geometry": len(maps) - with_geometry,
                "missing_maps": missing,
                "ambiguous_geometry_maps": ambiguous,
                "asset_status_counts": asset_counts,
            },
        }


def _resolution_manifest(resolution: MapAssetResolution, root: Path) -> dict:
    selected = resolution.selected
    return {
        "status": resolution.status,
        "reason": resolution.reason,
        "selected": _provider_manifest(selected, root) if selected else None,
        "providers": [_provider_manifest(provider, root) for provider in resolution.providers],
    }


def _provider_manifest(provider: MapAssetProvider, root: Path) -> dict:
    try:
        pk3 = str(provider.pk3_path.relative_to(root))
    except ValueError:
        pk3 = str(provider.pk3_path)
    return {
        "asset_kind": provider.asset_kind.value,
        "pk3": pk3,
        "member": provider.member,
        "member_index": provider.member_index,
        "size": provider.size,
        "crc32": f"{provider.crc32:08x}",
        "sha256": provider.sha256,
    }
