#!/usr/bin/env python3
"""Inkscape entry point for the searchable Iconify icon importer."""

from __future__ import annotations

import base64
import io
import tempfile
from math import ceil, sqrt
from pathlib import Path

import inkex
from inkex import command as inkex_command

from icon_importer.api import IconifyClient
from icon_importer.cache import DiskCache
from icon_importer.models import ImportChoice
from icon_importer.svg import (
    SvgValidationError,
    prepare_svg,
    svg_dimensions,
)


class IconImporterExtension(inkex.GenerateExtension):
    def effect(self):
        elements = self.generate()
        if not elements:
            return
        container = self.create_container()
        columns = ceil(sqrt(len(elements)))
        rows = ceil(len(elements) / columns)
        step = self._generated_display_size * 1.35
        for index, element in enumerate(elements):
            row = index // columns
            column = index % columns
            row_items = min(columns, len(elements) - row * columns)
            x = (column - (row_items - 1) / 2) * step
            y = (row - (rows - 1) / 2) * step
            placement = inkex.Group()
            placement.transform = inkex.Transform(translate=(x, y))
            placement.append(element)
            container.append(placement)

    """Open the icon browser and add its selected icon at the viewport center."""

    container_label = "Imported icon"
    container_layer = False

    def generate(self):
        try:
            from icon_importer.ui import IconBrowserDialog
        except (ImportError, ValueError) as exc:
            inkex.errormsg(
                "Icon Importer could not load its GTK interface.\n\n"
                "Use an official Inkscape build with Python GTK support.\n"
                f"Technical detail: {exc}"
            )
            return

        client = IconifyClient(cache=DiskCache.default())
        dialog = IconBrowserDialog(client)
        choices = dialog.run_and_get_choices()
        if not choices:
            return ()

        elements = []
        errors = []
        self._generated_display_size = self.svg.unittouu(
            f"{choices[0].size_px}px"
        )
        self.container_label = (
            choices[0].icon.full_name
            if len(choices) == 1
            else f"Imported icons ({len(choices)})"
        )
        for choice in choices:
            try:
                svg_bytes = client.fetch_svg(
                    choice.icon.full_name,
                    color=None if choice.preserve_colors else choice.color,
                )
                safe_svg = prepare_svg(
                    svg_bytes,
                    id_prefix=choice.unique_id_prefix,
                    stroke_scale=choice.stroke_scale,
                )
                if choice.import_format == "png":
                    element = self._make_png_image(
                        safe_svg, choice, self._generated_display_size
                    )
                else:
                    element = self._make_svg_group(
                        safe_svg, choice, self._generated_display_size
                    )
                elements.append(element)
            except (OSError, ValueError, SvgValidationError) as exc:
                errors.append(f"{choice.icon.full_name}: {exc}")
        if errors:
            inkex.errormsg(
                "Some icons could not be imported:\n\n" + "\n".join(errors)
            )
        return tuple(elements)

    @staticmethod
    def _copy_root_presentation(root, group):
        inherited = {
            "color",
            "fill",
            "fill-opacity",
            "fill-rule",
            "opacity",
            "paint-order",
            "shape-rendering",
            "stroke",
            "stroke-dasharray",
            "stroke-dashoffset",
            "stroke-linecap",
            "stroke-linejoin",
            "stroke-miterlimit",
            "stroke-opacity",
            "stroke-width",
            "style",
        }
        for key, value in root.attrib.items():
            if key in inherited:
                group.set(key, value)

    def _make_svg_group(
        self, safe_svg: bytes, choice: ImportChoice, display_size: float
    ):
        source_root = inkex.load_svg(io.BytesIO(safe_svg)).getroot()
        min_x, min_y, width, height = svg_dimensions(safe_svg)
        scale = display_size / max(width, height)

        group = inkex.Group()
        group.label = choice.icon.full_name
        group.set("data-icon-source", "Iconify")
        group.set("data-icon-name", choice.icon.full_name)
        if choice.icon.collection.license_title:
            group.set("data-icon-license", choice.icon.collection.license_title)
        if choice.icon.collection.license_url:
            group.set("data-icon-license-url", choice.icon.collection.license_url)

        artwork = inkex.Group()
        self._copy_root_presentation(source_root, artwork)
        for child in list(source_root):
            source_root.remove(child)
            artwork.append(child)

        center_x = min_x + width / 2
        center_y = min_y + height / 2
        artwork.transform = inkex.Transform(
            f"scale({scale}) translate({-center_x}, {-center_y})"
        )
        group.append(artwork)
        return group

    def _make_png_image(
        self, safe_svg: bytes, choice: ImportChoice, display_size: float
    ):
        png_bytes = self._render_png(safe_svg, choice.png_pixels)
        data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

        image = inkex.Image()
        image.label = choice.icon.full_name
        image.set("x", str(-display_size / 2))
        image.set("y", str(-display_size / 2))
        image.set("width", str(display_size))
        image.set("height", str(display_size))
        image.set("preserveAspectRatio", "xMidYMid meet")
        image.set("href", data_uri)
        image.set(inkex.addNS("href", "xlink"), data_uri)
        image.set("data-icon-source", "Iconify")
        image.set("data-icon-name", choice.icon.full_name)
        if choice.icon.collection.license_title:
            image.set("data-icon-license", choice.icon.collection.license_title)
        if choice.icon.collection.license_url:
            image.set("data-icon-license-url", choice.icon.collection.license_url)
        return image

    @staticmethod
    def _render_png(safe_svg: bytes, pixels: int) -> bytes:
        with tempfile.TemporaryDirectory(prefix="inkscape-icon-importer-") as temp:
            source = Path(temp) / "icon.svg"
            output = Path(temp) / "icon.png"

            root = inkex.load_svg(io.BytesIO(safe_svg)).getroot()
            root.set("width", str(pixels))
            root.set("height", str(pixels))
            inkex_command.write_svg(root.getroottree(), str(source))
            inkex_command.inkscape(
                str(source),
                export_filename=str(output),
                export_width=pixels,
                export_height=pixels,
                export_area_page=True,
            )
            if not output.exists():
                raise OSError("Inkscape did not create the requested PNG.")
            return output.read_bytes()


if __name__ == "__main__":
    IconImporterExtension().run()
