from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from icon_importer.svg import (
    SvgValidationError,
    prepare_svg,
    sanitize_svg,
    svg_dimensions,
)


SVG_NS = "http://www.w3.org/2000/svg"


class SvgTests(unittest.TestCase):
    def test_sanitizer_removes_scripts_events_and_external_links(self):
        source = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
            onload="bad()">
          <script>bad()</script>
          <path d="M0 0h1" onclick="bad()" fill="url(https://bad.test/a)"/>
          <use href="https://bad.test/icon.svg#x"/>
        </svg>"""
        root = sanitize_svg(source)

        self.assertNotIn("onload", root.attrib)
        self.assertEqual(len(root.findall(f"{{{SVG_NS}}}script")), 0)
        path = root.find(f"{{{SVG_NS}}}path")
        self.assertNotIn("onclick", path.attrib)
        self.assertNotIn("fill", path.attrib)
        use = root.find(f"{{{SVG_NS}}}use")
        self.assertNotIn("href", use.attrib)

    def test_prepare_svg_namespaces_ids_and_references(self):
        source = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -2 24 12">
          <defs><linearGradient id="paint"/></defs>
          <path id="shape" fill="url(#paint)" href="#shape"/>
        </svg>"""
        output = prepare_svg(source, "sample-")
        root = ET.fromstring(output)
        gradient = root.find(f".//{{{SVG_NS}}}linearGradient")
        path = root.find(f".//{{{SVG_NS}}}path")

        self.assertEqual(gradient.get("id"), "sample-paint")
        self.assertEqual(path.get("id"), "sample-shape")
        self.assertEqual(path.get("fill"), "url(#sample-paint)")
        self.assertEqual(path.get("href"), "#sample-shape")
        self.assertEqual(svg_dimensions(output), (-1.0, -2.0, 24.0, 12.0))

    def test_prepare_svg_scales_stroke_widths(self):
        source = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
          stroke-width="2"><path stroke-width="1.5px"
          style="fill:none; stroke-width: 0.5"/></svg>"""
        root = ET.fromstring(prepare_svg(source, stroke_scale=1.5))
        path = root.find(f"{{{SVG_NS}}}path")

        self.assertEqual(root.get("stroke-width"), "3")
        self.assertEqual(path.get("stroke-width"), "2.25px")
        self.assertIn("stroke-width: 0.75", path.get("style"))


    def test_rejects_doctype(self):
        source = b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///x">]><svg>&x;</svg>'
        with self.assertRaises(SvgValidationError):
            sanitize_svg(source)

    def test_requires_positive_dimensions(self):
        with self.assertRaises(SvgValidationError):
            svg_dimensions(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 0 24"/>')


if __name__ == "__main__":
    unittest.main()
