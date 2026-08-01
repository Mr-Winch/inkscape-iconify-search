"""Data models shared by the API, user interface, and Inkscape entry point."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class CollectionInfo:
    prefix: str
    name: str
    total: int = 0
    version: str = ""
    author_name: str = ""
    author_url: str = ""
    license_title: str = ""
    license_spdx: str = ""
    license_url: str = ""
    category: str = "Uncategorized"
    palette: bool = False
    height: int = 0
    display_height: int = 0
    tags: tuple[str, ...] = ()
    samples: tuple[str, ...] = ()

    @classmethod
    def from_api(cls, prefix: str, payload: dict | None) -> "CollectionInfo":
        payload = payload or {}
        author = payload.get("author") or {}
        license_info = payload.get("license") or {}
        return cls(
            prefix=prefix,
            name=str(payload.get("name") or prefix),
            total=int(payload.get("total") or 0),
            version=str(payload.get("version") or ""),
            author_name=str(author.get("name") or ""),
            author_url=str(author.get("url") or ""),
            license_title=str(license_info.get("title") or ""),
            license_spdx=str(license_info.get("spdx") or ""),
            license_url=str(license_info.get("url") or ""),
            category=str(payload.get("category") or "Uncategorized"),
            palette=bool(payload.get("palette")),
            height=int(payload.get("height") or 0),
            display_height=int(payload.get("displayHeight") or 0),
            tags=tuple(str(item) for item in (payload.get("tags") or ())),
            samples=tuple(str(item) for item in (payload.get("samples") or ())),
        )


@dataclass(frozen=True)
class IconInfo:
    full_name: str
    prefix: str
    name: str
    collection: CollectionInfo


@dataclass(frozen=True)
class SearchResult:
    icons: tuple[IconInfo, ...]
    total: int
    start: int
    limit: int
    collections: dict[str, CollectionInfo] = field(default_factory=dict)


@dataclass(frozen=True)
class CollectionBrowseResult:
    prefix: str
    total: int
    icons: tuple[str, ...]
    categories: dict[str, tuple[str, ...]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    hidden: tuple[str, ...] = ()
    chars: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportChoice:
    icon: IconInfo
    import_format: str
    size_px: float
    png_pixels: int
    color: str
    stroke_scale: float
    preserve_colors: bool
    unique_id_prefix: str = field(
        default_factory=lambda: f"icon-{uuid4().hex[:10]}-"
    )
