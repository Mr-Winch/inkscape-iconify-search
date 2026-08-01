from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from icon_importer.api import IconifyClient
from icon_importer.cache import DiskCache


class StubClient(IconifyClient):
    def __init__(self, response: dict):
        super().__init__(cache=None, base_urls=("https://example.test",))
        self.response = response
        self.urls = []

    def _download(self, url: str) -> bytes:
        self.urls.append(url)
        return json.dumps(self.response).encode("utf-8")


class IconifyClientTests(unittest.TestCase):
    def test_search_parses_icons_and_license_metadata(self):
        client = StubClient(
            {
                "icons": ["tabler:home", "not valid"],
                "total": 1,
                "limit": 32,
                "start": 0,
                "collections": {
                    "tabler": {
                        "name": "Tabler Icons",
                        "total": 6000,
                        "author": {"name": "Author", "url": "https://example.test"},
                        "license": {
                            "title": "MIT",
                            "spdx": "MIT",
                            "url": "https://example.test/license",
                        },
                    }
                },
            }
        )

        result = client.search("home", prefix="tabler")

        self.assertEqual(result.total, 1)
        self.assertEqual(result.icons[0].full_name, "tabler:home")
        self.assertEqual(result.icons[0].collection.license_spdx, "MIT")
        self.assertIn("query=home", client.urls[0])
        self.assertIn("prefix=tabler", client.urls[0])

    def test_fetch_svg_validates_icon_name(self):
        client = StubClient({})
        with self.assertRaises(ValueError):
            client.fetch_svg("../bad")

    def test_disk_cache_round_trip(self):
        test_temp_root = os.environ.get("ICON_IMPORTER_TEST_TMP")
        with tempfile.TemporaryDirectory(
            dir=Path(test_temp_root) if test_temp_root else None
        ) as directory:
            cache = DiskCache(Path(directory))
            cache.put("key", b"value")
            self.assertEqual(cache.get("key", 60), b"value")

    def test_settings_round_trip_between_cache_instances(self):
        test_temp_root = os.environ.get("ICON_IMPORTER_TEST_TMP")
        with tempfile.TemporaryDirectory(
            dir=Path(test_temp_root) if test_temp_root else None
        ) as directory:
            cache = DiskCache(Path(directory))
            cache.put_setting("dark_theme", True)
            cache.put_setting("icon_color", "#12ab34")
            ui_state = {
                "import_size": 72,
                "result_limit": 160,
                "zoom": 80,
                "filters": {"style": "stroke", "similar": False},
                "collections": {"use_all": False, "prefixes": ["tabler"]},
            }
            cache.put_setting("ui_state", ui_state)
            reopened = DiskCache(Path(directory))
            self.assertIs(reopened.get_setting("dark_theme"), True)
            self.assertEqual(reopened.get_setting("icon_color"), "#12ab34")
            self.assertEqual(reopened.get_setting("ui_state"), ui_state)
            self.assertEqual(reopened.get_setting("missing", "fallback"), "fallback")

if __name__ == "__main__":
    unittest.main()
