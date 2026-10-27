const cleanText = (value) => String(value ?? "").trim();
const randomId = () => globalThis.crypto?.randomUUID?.() || `section-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function normalizeFavorites(value) {
  const sections = Array.isArray(value?.sections) ? value.sections : [];
  const usedIds = new Set();
  return {
    sections: sections.flatMap((section) => {
      const name = cleanText(section?.name);
      if (!name) return [];
      let id = cleanText(section.id) || randomId();
      if (usedIds.has(id)) id = randomId();
      usedIds.add(id);
      const icons = [...new Set(
        (Array.isArray(section.icons) ? section.icons : [])
          .map(cleanText)
          .filter((icon) => /^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$/.test(icon))
      )];
      return [{ id, name, icons }];
    })
  };
}

export function createFavoriteSection(favorites, name, id = randomId()) {
  const next = normalizeFavorites(favorites);
  const cleanName = cleanText(name);
  if (!cleanName) throw new Error("A favorites section name is required.");
  next.sections.push({ id, name: cleanName, icons: [] });
  return { favorites: next, sectionId: id };
}

export function addFavorite(favorites, sectionId, iconName) {
  const next = normalizeFavorites(favorites);
  const section = next.sections.find((item) => item.id === sectionId);
  if (!section) throw new Error("The selected favorites section no longer exists.");
  const added = !section.icons.includes(iconName);
  if (added) section.icons.push(iconName);
  return { favorites: next, added };
}

export function removeFavorite(favorites, sectionId, iconName) {
  const next = normalizeFavorites(favorites);
  const section = next.sections.find((item) => item.id === sectionId);
  if (section) section.icons = section.icons.filter((name) => name !== iconName);
  return next;
}

export function removeFavoriteSection(favorites, sectionId) {
  const next = normalizeFavorites(favorites);
  next.sections = next.sections.filter((section) => section.id !== sectionId);
  return next;
}

export function isFavorite(favorites, iconName) {
  return normalizeFavorites(favorites).sections.some((section) => section.icons.includes(iconName));
}

export function favoriteCount(favorites) {
  return normalizeFavorites(favorites).sections.reduce((total, section) => total + section.icons.length, 0);
}
