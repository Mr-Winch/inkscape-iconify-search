"""Validation and sanitization for remotely retrieved SVG icons."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

BLOCKED_ELEMENTS = {
    "audio",
    "foreignObject",
    "iframe",
    "object",
    "script",
    "style",
    "video",
}
URL_REFERENCE_RE = re.compile(r"url\(\s*(['\"]?)#([^)'\"]+)\1\s*\)")
NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)
STROKE_WIDTH_IN_STYLE_RE = re.compile(
    r"(?P<prefix>(?:^|;)\s*stroke-width\s*:\s*)"
    r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[A-Za-z%]*)",
    re.IGNORECASE,
)


class SvgValidationError(ValueError):
    """Raised when downloaded SVG cannot be imported safely."""


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _is_dangerous_style(value: str) -> bool:
    lowered = value.lower().replace(" ", "")
    if any(token in lowered for token in ("javascript:", "expression(", "@import")):
        return True
    for match in re.finditer(r"url\((.*?)\)", value, flags=re.IGNORECASE):
        target = match.group(1).strip(" \t\r\n'\"")
        if not target.startswith("#"):
            return True
    return False


def _safe_href(element_name: str, value: str) -> bool:
    stripped = value.strip()
    if stripped.startswith("#"):
        return True
    if element_name == "image" and stripped.lower().startswith(
        ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
    ):
        return True
    return False


def sanitize_svg(svg_data: bytes | str) -> ET.Element:
    if isinstance(svg_data, str):
        raw = svg_data.encode("utf-8")
    else:
        raw = svg_data
    if len(raw) > 2_000_000:
        raise SvgValidationError("The SVG exceeds the 2 MB safety limit.")

    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise SvgValidationError("SVG document types and entities are not allowed.")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SvgValidationError(f"Invalid SVG: {exc}") from exc
    if _local_name(root.tag) != "svg":
        raise SvgValidationError("The downloaded document is not an SVG.")

    def clean(parent: ET.Element) -> None:
        for child in list(parent):
            if _local_name(child.tag) in BLOCKED_ELEMENTS:
                parent.remove(child)
                continue
            clean(child)

        element_name = _local_name(parent.tag)
        for key, value in list(parent.attrib.items()):
            attr_name = _local_name(key)
            lower_name = attr_name.lower()
            if lower_name.startswith("on") or key == f"{{{XML_NS}}}base":
                del parent.attrib[key]
                continue
            if lower_name in {"href", "src"} and not _safe_href(element_name, value):
                del parent.attrib[key]
                continue
            if lower_name == "style" and _is_dangerous_style(value):
                del parent.attrib[key]
                continue
            if lower_name in {
                "fill",
                "stroke",
                "filter",
                "clip-path",
                "mask",
                "marker",
                "marker-start",
                "marker-mid",
                "marker-end",
            } and _is_dangerous_style(value):
                del parent.attrib[key]

    clean(root)
    return root


def _rewrite_reference(value: str, id_map: dict[str, str]) -> str:
    if value.startswith("#"):
        return "#" + id_map.get(value[1:], value[1:])

    def replace(match: re.Match) -> str:
        quote = match.group(1)
        identifier = match.group(2)
        return f"url({quote}#{id_map.get(identifier, identifier)}{quote})"

    return URL_REFERENCE_RE.sub(replace, value)


def namespace_ids(root: ET.Element, prefix: str) -> None:
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]", "-", prefix)
    id_map: dict[str, str] = {}
    for element in root.iter():
        old_id = element.get("id")
        if old_id:
            new_id = safe_prefix + old_id
            id_map[old_id] = new_id
            element.set("id", new_id)

    if not id_map:
        return
    for element in root.iter():
        for key, value in list(element.attrib.items()):
            if "#" in value:
                element.set(key, _rewrite_reference(value, id_map))


def scale_stroke_widths(root: ET.Element, factor: float) -> None:
    """Scale numeric stroke widths while preserving their optional units."""
    if not 0.1 <= factor <= 4.0:
        raise ValueError("Stroke scale must be between 10% and 400%.")

    def scaled(value: str) -> str:
        match = re.fullmatch(
            r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([A-Za-z%]*)\s*",
            value,
        )
        if not match:
            return value
        number = float(match.group(1))
        if number < 0:
            return value
        return f"{number * factor:g}{match.group(2)}"

    for element in root.iter():
        value = element.get("stroke-width")
        if value is not None:
            element.set("stroke-width", scaled(value))
        style = element.get("style")
        if not style:
            continue
        updated = STROKE_WIDTH_IN_STYLE_RE.sub(
            lambda match: match.group("prefix") + scaled(match.group("value")), style
        )
        if updated != style:
            element.set("style", updated)


def classify_svg_style(svg_data: bytes | str) -> str:
    """Classify an SVG as filled, stroke, or mixed using inherited paint."""
    try:
        root = ET.fromstring(svg_data)
    except ET.ParseError:
        return "mixed"
    shape_names = {
        "circle", "ellipse", "line", "path", "polygon", "polyline", "rect", "text"
    }
    has_fill = False
    has_stroke = False

    def paint_values(element: ET.Element, fill: str, stroke: str) -> None:
        nonlocal has_fill, has_stroke
        style_values: dict[str, str] = {}
        for declaration in (element.get("style") or "").split(";"):
            if ":" in declaration:
                key, value = declaration.split(":", 1)
                style_values[key.strip().lower()] = value.strip()
        current_fill = style_values.get("fill", element.get("fill", fill)).strip().lower()
        current_stroke = style_values.get(
            "stroke", element.get("stroke", stroke)
        ).strip().lower()
        if _local_name(element.tag) in shape_names:
            has_fill = has_fill or current_fill not in {"", "none", "transparent"}
            has_stroke = has_stroke or current_stroke not in {"", "none", "transparent"}
        for child in element:
            paint_values(child, current_fill, current_stroke)

    paint_values(root, "black", "none")
    if has_fill and has_stroke:
        return "mixed"
    if has_stroke:
        return "stroke"
    return "fill"

def prepare_svg(
    svg_data: bytes | str,
    id_prefix: str = "imported-icon-",
    stroke_scale: float = 1.0,
) -> bytes:
    root = sanitize_svg(svg_data)
    namespace_ids(root, id_prefix)
    scale_stroke_widths(root, stroke_scale)
    # Verify dimensions before returning a normalized document.
    svg_dimensions(ET.tostring(root, encoding="utf-8"))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def svg_dimensions(svg_data: bytes | str) -> tuple[float, float, float, float]:
    try:
        root = ET.fromstring(svg_data)
    except ET.ParseError as exc:
        raise SvgValidationError(f"Invalid SVG: {exc}") from exc

    view_box = root.get("viewBox") or root.get("viewbox")
    if view_box:
        parts = re.split(r"[\s,]+", view_box.strip())
        if len(parts) != 4 or not all(NUMBER_RE.fullmatch(part) for part in parts):
            raise SvgValidationError("SVG has an invalid viewBox.")
        min_x, min_y, width, height = map(float, parts)
    else:
        width = _plain_number(root.get("width"))
        height = _plain_number(root.get("height"))
        min_x = min_y = 0.0

    if width <= 0 or height <= 0:
        raise SvgValidationError("SVG dimensions must be greater than zero.")
    if max(abs(min_x), abs(min_y), width, height) > 1_000_000:
        raise SvgValidationError("SVG dimensions exceed the safety limit.")
    return min_x, min_y, width, height


def _plain_number(value: str | None) -> float:
    if not value:
        raise SvgValidationError("SVG is missing both viewBox and numeric dimensions.")
    match = re.fullmatch(
        r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
        r"(?:px)?\s*",
        value,
    )
    if not match:
        raise SvgValidationError(
            "SVG dimensions must be numeric pixels when no viewBox is present."
        )
    return float(match.group(1))
