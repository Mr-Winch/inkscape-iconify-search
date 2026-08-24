from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from icon_importer import __version__
from tools.package_extension import ARCHIVE_NAME, build, write_sha256


ROOT = Path(__file__).resolve().parents[1]
INKSCAPE_NS = {"i": "http://www.inkscape.org/namespace/inkscape/extension"}


class ExtensionIdentityTests(unittest.TestCase):
    def test_public_version_is_aligned(self):
        self.assertEqual(__version__, "0.6.3")
        self.assertEqual(ARCHIVE_NAME, "inkscape-iconify-search-v0.6.3.zip")
        for filename in ("icon_importer.inx", "install.cmd", "uninstall.cmd", "README.md", "CHANGELOG.md"):
            content = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn(__version__, content, filename)

    def test_manifest_references_supplied_icon(self):
        root = ET.parse(ROOT / "icon_importer.inx").getroot()
        icon = root.find(".//i:effect/i:icon", INKSCAPE_NS)
        self.assertIsNotNone(icon)
        self.assertEqual(icon.text, "iconify_search_icon.svg")
        self.assertTrue((ROOT / icon.text).is_file())

    def test_installer_and_zip_include_icon(self):
        installer = (ROOT / "install.cmd").read_text(encoding="utf-8")
        self.assertGreaterEqual(installer.count("iconify_search_icon.svg"), 2)
        self.assertGreaterEqual(installer.count("favorites.py"), 2)
        with tempfile.TemporaryDirectory() as directory:
            archive_path = build(Path(directory) / "extension.zip")
            checksum_path = write_sha256(archive_path)
            with ZipFile(archive_path) as archive:
                self.assertIn("iconify_search_icon.svg", archive.namelist())
                self.assertIn("icon_importer/favorites.py", archive.namelist())
                self.assertIn("uninstall.cmd", archive.namelist())
                self.assertIn("CHANGELOG.md", archive.namelist())
            checksum, filename = checksum_path.read_text(encoding="ascii").split()
            self.assertEqual(len(checksum), 64)
            self.assertEqual(filename, archive_path.name)


if __name__ == "__main__":
    unittest.main()
