from __future__ import annotations

import json
import ssl
import unittest
import urllib.error

from icon_importer.api import IconifyClient
from icon_importer.models import CollectionInfo
from icon_importer.svg import classify_svg_style


class StubClient(IconifyClient):
    def __init__(self, response: dict):
        super().__init__(cache=None, base_urls=("https://example.test",))
        self.response = response
        self.urls: list[str] = []

    def _download(self, url: str) -> bytes:
        self.urls.append(url)
        return json.dumps(self.response).encode("utf-8")


class CertificateFallbackClient(IconifyClient):
    def __init__(self):
        super().__init__(cache=None)
        self.curl_used = False

    def _urllib_download(self, url, context=None):
        raise urllib.error.URLError(
            ssl.SSLCertVerificationError(1, "CERTIFICATE_VERIFY_FAILED")
        )

    def _get_windows_trust_context(self):
        return None

    def _curl_download(self, url):
        self.curl_used = True
        return b"secure fallback"


class EnhancedApiTests(unittest.TestCase):
    def test_collection_metadata_is_preserved(self):
        item = CollectionInfo.from_api("demo", {
            "name": "Demo Icons",
            "total": 25,
            "category": "General",
            "palette": True,
            "height": 24,
            "displayHeight": 32,
            "tags": ["sample"],
            "samples": ["home"],
            "license": {"title": "MIT License", "spdx": "MIT"},
        })
        self.assertEqual(item.category, "General")
        self.assertTrue(item.palette)
        self.assertEqual(item.height, 24)
        self.assertEqual(item.display_height, 32)
        self.assertEqual(item.license_spdx, "MIT")
        self.assertEqual(item.samples, ("home",))

    def test_dynamic_collection_catalog(self):
        client = StubClient({
            "tabler": {"name": "Tabler Icons", "total": 6000},
            "mdi": {"name": "Material Design Icons", "total": 7000},
        })
        result = client.list_collections()
        self.assertEqual([item.prefix for item in result], ["mdi", "tabler"])
        self.assertIn("/collections", client.urls[0])

    def test_collection_browse_parses_filters(self):
        client = StubClient({
            "total": 3,
            "uncategorized": ["home"],
            "categories": {"Arrows": ["arrow-left"]},
            "aliases": {"house": "home"},
            "hidden": ["old-home"],
            "chars": {"e001": "home"},
        })
        result = client.browse_collection("tabler")
        self.assertEqual(result.icons, ("home", "arrow-left"))
        self.assertEqual(result.categories["Arrows"], ("arrow-left",))
        self.assertEqual(result.aliases["house"], "home")
        self.assertEqual(result.hidden, ("old-home",))
        self.assertEqual(result.chars["e001"], "home")

    def test_search_exposes_iconify_query_filters(self):
        client = StubClient({"icons": [], "total": 0, "limit": 64, "start": 2})
        client.search(
            "arrow", prefixes=("tabler", "mdi"), category="General",
            similar=False, start=2,
        )
        url = client.urls[0]
        self.assertIn("prefixes=tabler%2Cmdi", url)
        self.assertIn("category=General", url)
        self.assertIn("similar=false", url)
        self.assertIn("start=2", url)

    def test_certificate_error_uses_verified_system_fallback(self):
        client = CertificateFallbackClient()
        self.assertEqual(client._download("https://api.iconify.design"), b"secure fallback")
        self.assertTrue(client.curl_used)

    def test_svg_style_classification(self):
        outline = b'<svg fill="none" stroke="currentColor"><path d="M0 0"/></svg>'
        solid = b'<svg><path d="M0 0"/></svg>'
        mixed = b'<svg><path fill="red" stroke="blue" d="M0 0"/></svg>'
        self.assertEqual(classify_svg_style(outline), "stroke")
        self.assertEqual(classify_svg_style(solid), "fill")
        self.assertEqual(classify_svg_style(mixed), "mixed")


if __name__ == "__main__":
    unittest.main()
