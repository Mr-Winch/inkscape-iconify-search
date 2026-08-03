import unittest

from icon_importer.favorites import (
    add_icon,
    contains_icon,
    create_section,
    icon_count,
    normalize_favorites,
    remove_icon,
    remove_section,
)


class FavoritesTests(unittest.TestCase):
    def test_create_add_and_deduplicate(self):
        favorites, section_id = create_section({}, "Navigation")
        favorites = add_icon(favorites, section_id, "tabler:home")
        favorites = add_icon(favorites, section_id, "tabler:home")
        self.assertTrue(contains_icon(favorites, "tabler:home"))
        self.assertEqual(icon_count(favorites), 1)

    def test_remove_icon_and_section(self):
        favorites, section_id = create_section({}, "Actions")
        favorites = add_icon(favorites, section_id, "tabler:plus")
        favorites = remove_icon(favorites, section_id, "tabler:plus")
        self.assertEqual(favorites["sections"][0]["icons"], [])
        favorites = remove_section(favorites, section_id)
        self.assertEqual(favorites, {"sections": []})

    def test_normalize_rejects_invalid_and_duplicate_values(self):
        favorites = normalize_favorites({"sections": [{
            "id": "one",
            "name": " Saved ",
            "icons": ["mdi:home", "mdi:home", "invalid"],
        }, None, {"name": ""}]})
        self.assertEqual(favorites["sections"][0]["name"], "Saved")
        self.assertEqual(favorites["sections"][0]["icons"], ["mdi:home"])


if __name__ == "__main__":
    unittest.main()
