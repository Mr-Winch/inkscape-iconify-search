"""Persistent favorites model shared by the GTK interface and tests."""

from __future__ import annotations

from uuid import uuid4


def normalize_favorites(value):
    """Return a safe, JSON-serializable favorites structure."""
    sections = value.get("sections", ()) if isinstance(value, dict) else ()
    normalized = []
    seen_section_ids = set()
    for section in sections if isinstance(sections, (list, tuple)) else ():
        if not isinstance(section, dict):
            continue
        name = str(section.get("name") or "").strip()
        if not name:
            continue
        section_id = str(section.get("id") or uuid4().hex)
        if section_id in seen_section_ids:
            section_id = uuid4().hex
        seen_section_ids.add(section_id)
        icons = []
        seen_icons = set()
        raw_icons = section.get("icons", ())
        for icon in raw_icons if isinstance(raw_icons, (list, tuple)) else ():
            full_name = str(icon or "").strip()
            if ":" not in full_name or full_name in seen_icons:
                continue
            seen_icons.add(full_name)
            icons.append(full_name)
        normalized.append({"id": section_id, "name": name, "icons": icons})
    return {"sections": normalized}


def create_section(favorites, name):
    favorites = normalize_favorites(favorites)
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("A section name is required.")
    section = {"id": uuid4().hex, "name": clean_name, "icons": []}
    favorites["sections"].append(section)
    return favorites, section["id"]


def add_icon(favorites, section_id, full_name):
    favorites = normalize_favorites(favorites)
    for section in favorites["sections"]:
        if section["id"] == section_id:
            if full_name not in section["icons"]:
                section["icons"].append(full_name)
            return favorites
    raise KeyError(section_id)


def remove_icon(favorites, section_id, full_name):
    favorites = normalize_favorites(favorites)
    for section in favorites["sections"]:
        if section["id"] == section_id:
            section["icons"] = [icon for icon in section["icons"] if icon != full_name]
            break
    return favorites


def remove_section(favorites, section_id):
    favorites = normalize_favorites(favorites)
    favorites["sections"] = [
        section for section in favorites["sections"] if section["id"] != section_id
    ]
    return favorites


def contains_icon(favorites, full_name):
    return any(
        full_name in section["icons"]
        for section in normalize_favorites(favorites)["sections"]
    )


def icon_count(favorites):
    return sum(
        len(section["icons"])
        for section in normalize_favorites(favorites)["sections"]
    )
