import test from "node:test";
import assert from "node:assert/strict";
import { addFavorite, createFavoriteSection, favoriteCount, normalizeFavorites, removeFavorite, removeFavoriteSection } from "../src/favorites.js";

test("normalizes invalid and duplicate icons", () => {
  const value = normalizeFavorites({ sections: [{ id: "a", name: " UI ", icons: ["lucide:home", "lucide:home", "bad"] }] });
  assert.deepEqual(value.sections[0], { id: "a", name: "UI", icons: ["lucide:home"] });
});

test("creates sections and manages individual favorites", () => {
  const created = createFavoriteSection({}, "Navigation", "nav");
  const added = addFavorite(created.favorites, "nav", "lucide:home");
  assert.equal(added.added, true);
  assert.equal(favoriteCount(added.favorites), 1);
  assert.equal(addFavorite(added.favorites, "nav", "lucide:home").added, false);
  assert.equal(favoriteCount(removeFavorite(added.favorites, "nav", "lucide:home")), 0);
  assert.equal(removeFavoriteSection(added.favorites, "nav").sections.length, 0);
});
