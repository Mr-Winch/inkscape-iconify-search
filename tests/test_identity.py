from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from tools.package_extension import build


ROOT = Path(__file__).resolve().parents[1]
INKSCAPE_NS = {"i": "http://www.inkscape.org/namespace/inkscape/extension"}


class ExtensionIdentityTests(unittest.TestCase):
    def test_manifest_references_supplied_icon(self):
        root = ET.parse(ROOT / "icon_importer.inx").getroot()
        icon = root.find(".//i:effect/i:icon", INKSCAPE_NS)
        self.assertIsNotNone(icon)
        self.assertEqual(icon.text, "iconify_search_icon.svg")
        self.assertTrue((ROOT / icon.text).is_file())

    def test_installer_and_zip_include_icon(self):
        installer = (ROOT / "install.cmd").read_text(encoding="utf-8")
        self.assertGreaterEqual(installer.count("iconify_search_icon.svg"), 2)
        with tempfile.TemporaryDirectory() as directory:
            archive_path = build(Path(directory) / "extension.zip")
            with ZipFile(archive_path) as archive:
                self.assertIn("iconify_search_icon.svg", archive.namelist())


if __name__ == "__main__":
    unittest.main()