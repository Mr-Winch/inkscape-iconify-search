import { IconifyApi, buildIconUrl, sanitizeSvg, svgToPngBlob } from "./iconify-api.js";
import { addFavorite, createFavoriteSection, favoriteCount, isFavorite, normalizeFavorites, removeFavorite, removeFavoriteSection } from "./favorites.js";
import { styles } from "./styles.js";

export const VERSION = "1.0.0";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
const iconLabel = (name) => name.includes(":") ? name.slice(name.indexOf(":") + 1) : name;
const APP_ICON_URL = new URL("../assets/iconify_search_icon.svg", import.meta.url).href;
const svgIcon = (name) => ({
  theme: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="m16 16 4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  loading: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="34 16"/></svg>',
  star: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.75 5.57 6.15.9-4.45 4.33 1.05 6.12L12 17.03l-5.5 2.89 1.05-6.12L3.1 9.47l6.15-.9L12 3Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
  starSaved: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.75 5.57 6.15.9-4.45 4.33 1.05 6.12L12 17.03l-5.5 2.89 1.05-6.12L3.1 9.47l6.15-.9L12 3Z" fill="currentColor" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg>',
  trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
})[name];
const DEFAULT_FILTERS = Object.freeze({ category: "", palette: "", style: "", license: "", grid: "", iconCategory: "", similar: true, aliases: false, hidden: false, start: 0 });
const normalizeFilters = (value = {}) => ({
  category: String(value.category || ""), palette: String(value.palette || ""),
  style: String(value.style || ""), license: String(value.license || ""),
  grid: String(value.grid || ""), iconCategory: String(value.iconCategory || ""),
  similar: value.similar !== false, aliases: value.aliases === true,
  hidden: value.hidden === true, start: Math.max(0, Number(value.start) || 0)
});

export class IconifyAssetPicker extends HTMLElement {
  static observedAttributes = ["theme", "storage-key"];

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.pickerStyleSheet = new CSSStyleSheet();
    this.pickerStyleSheet.replaceSync(styles);
    this.shadowRoot.adoptedStyleSheets = [this.pickerStyleSheet];
    this.api = new IconifyApi();
    this.collections = [];
    this.results = [];
    this.total = 0;
    this.selected = new Set();
    this.favorites = { sections: [] };
    this.activeTab = "filters";
    this.format = "svg";
    this.searchController = null;
    this.loading = false;
    this.collectionBrowse = null;
  }

  get storageKey() { return this.getAttribute("storage-key") || "iconify-asset-picker"; }
  get multiple() { return !this.hasAttribute("single"); }

  connectedCallback() {
    this.loadPreferences();
    this.resolveTheme();
    this.render();
    this.bind();
    this.loadCollections();
  }

  disconnectedCallback() { this.searchController?.abort(); }
  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue || !this.isConnected) return;
    if (name === "theme") this.resolveTheme();
    if (name === "storage-key") { this.loadPreferences(); this.renderDynamic(); }
  }

  resolveTheme() {
    const requested = this.getAttribute("theme") || "auto";
    const dark = requested === "dark" || (requested === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
    this.setAttribute("data-resolved-theme", dark ? "dark" : "light");
    if (this.shadowRoot.querySelector(".results")) { this.renderResults(); this.renderSidebar(); }
  }

  loadPreferences() {
    try {
      const saved = JSON.parse(localStorage.getItem(`${this.storageKey}:preferences`) || "{}");
      this.limit = Number(saved.limit) || 120;
      this.size = Number(saved.size) || 64;
      this.zoom = Math.max(36, Math.min(88, Number(saved.zoom) || 52));
      this.pngPixels = Number(saved.pngPixels) || 512;
      this.color = saved.color || "#202124";
      this.collectionPrefix = saved.prefix || "";
      this.format = saved.format === "png" ? "png" : "svg";
      this.filters = normalizeFilters(saved.filters);
      this.favorites = normalizeFavorites(JSON.parse(localStorage.getItem(`${this.storageKey}:favorites`) || "{}"));
    } catch {
      this.limit = 120; this.size = 64; this.zoom = 52; this.pngPixels = 512; this.color = "#202124"; this.collectionPrefix = ""; this.format = "svg"; this.filters = normalizeFilters(); this.favorites = { sections: [] };
    }
  }

  savePreferences() {
    localStorage.setItem(`${this.storageKey}:preferences`, JSON.stringify({ limit: this.limit, size: this.size, zoom: this.zoom, pngPixels: this.pngPixels, color: this.color, prefix: this.collectionPrefix, format: this.format, filters: this.filters }));
  }

  saveFavorites() {
    localStorage.setItem(`${this.storageKey}:favorites`, JSON.stringify(this.favorites));
    this.dispatchEvent(new CustomEvent("iconify-favorites-change", { bubbles: true, composed: true, detail: { favorites: structuredClone(this.favorites) } }));
  }

  render() {
    this.shadowRoot.innerHTML = `<section class="app" aria-label="Iconify asset picker">
        <header class="header"><div class="mark" aria-hidden="true"><img src="${APP_ICON_URL}" alt=""></div><div><div class="title">Iconify Asset Picker</div><div class="subtitle">v${VERSION} · Search open-source icon collections and import SVG or PNG</div></div><button class="theme icon-button" type="button" title="Switch theme" aria-label="Switch theme">${svgIcon("theme")}</button></header>
        <form class="searchbar"><input name="query" type="search" autocomplete="off" placeholder="Search icons — try arrow, camera, user, chart…" aria-label="Search icons"><button class="primary" type="submit">Search</button></form>
        <div class="body">
          <aside class="sidebar"><nav class="tabs"><button class="tab active" data-tab="filters" type="button">Filters <span class="filter-marker" aria-hidden="true"></span></button><button class="tab" data-tab="favorites" type="button">Favorites <span class="favorite-count"></span></button></nav><div class="side-content"></div></aside>
          <main class="main"><div class="toolbar"><strong>Icons</strong><span class="count"></span><span class="spacer"></span><label class="zoom-control"><span>Zoom</span><input name="zoom" type="range" min="36" max="88" step="4" aria-label="Icon preview size"></label><button class="clear" type="button" disabled>Clear selection</button></div><div class="grid-wrap"><div class="results empty"><div><div class="empty-icon">${svgIcon("search")}</div><strong>Search the Iconify catalog</strong><div>Enter at least two characters to begin.</div></div></div></div><div class="status" role="status">Ready.</div></main>
        </div>
        <footer class="footer"><div class="options">
          <div class="compact"><label>Format</label><div class="format"><button type="button" data-format="svg">SVG</button><button type="button" data-format="png">PNG</button></div></div>
          <div class="compact"><label for="asset-size">Asset size</label><input id="asset-size" name="size" type="number" min="8" max="2048" step="8"></div>
          <div class="compact png-option"><label for="png-pixels">PNG pixels</label><input id="png-pixels" name="pngPixels" type="number" min="16" max="4096" step="16"></div>
          <div class="compact"><label for="asset-color">Icon color</label><input id="asset-color" name="color" type="color"></div>
        </div><div class="actions"><button class="clear footer-clear" type="button" disabled>Clear all</button><button class="primary import" type="button" disabled>Import selected</button></div></footer>
      </section>
      <dialog><form class="dialog-content" method="dialog"><h2>Add to favorites</h2><p class="dialog-icon"></p><div class="field"><label for="favorite-section">Existing section</label><select id="favorite-section" name="favoriteSection"></select></div><div class="field"><label for="new-section">Or create a section</label><input id="new-section" name="newSection" maxlength="60" placeholder="e.g. Navigation"></div><div class="dialog-error error" role="alert"></div><div class="dialog-actions"><button value="cancel">Cancel</button><button class="primary save-favorite" value="default">Save</button></div></form></dialog>`;
    this.renderDynamic();
  }

  bind() {
    const root = this.shadowRoot;
    root.querySelector(".searchbar").addEventListener("submit", (event) => { event.preventDefault(); this.search(); });
    root.querySelector(".theme").addEventListener("click", () => { const dark = this.getAttribute("data-resolved-theme") === "dark"; this.setAttribute("theme", dark ? "light" : "dark"); });
    root.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => { this.activeTab = button.dataset.tab; this.renderDynamic(); }));
    root.querySelectorAll(".clear").forEach((button) => button.addEventListener("click", () => this.clearSelection()));
    root.querySelectorAll("[data-format]").forEach((button) => button.addEventListener("click", () => { this.format = button.dataset.format; this.savePreferences(); this.renderOptions(); }));
    root.querySelector('[name="size"]').addEventListener("change", (event) => { this.size = Math.max(8, Math.min(2048, Number(event.target.value) || 64)); this.savePreferences(); });
    root.querySelector('[name="pngPixels"]').addEventListener("change", (event) => { this.pngPixels = Math.max(16, Math.min(4096, Number(event.target.value) || 512)); this.savePreferences(); });
    root.querySelector('[name="color"]').addEventListener("input", (event) => { this.color = event.target.value; this.savePreferences(); this.renderResults(); });
    root.querySelector('[name="zoom"]').addEventListener("input", (event) => { this.zoom = Math.max(36, Math.min(88, Number(event.target.value) || 52)); this.savePreferences(); this.applyZoom(); });
    root.querySelector(".import").addEventListener("click", () => this.importSelected());
    root.querySelector("dialog form").addEventListener("submit", (event) => this.saveFavoriteFromDialog(event));
  }

  previewColor() { return this.getAttribute("data-resolved-theme") === "dark" ? "#ffffff" : this.color; }

  previewUrl(name) {
    const prefix = name.split(":", 1)[0];
    const collection = this.collections.find((item) => item.prefix === prefix);
    return buildIconUrl(name, { color: collection?.palette ? "" : this.previewColor() });
  }

  advancedFiltersActive() {
    const filters = this.filters;
    return Boolean(filters.category || filters.palette || filters.style || filters.license || filters.grid || filters.iconCategory || !filters.similar || filters.aliases || filters.hidden || filters.start);
  }

  filtersActive() { return Boolean(this.collectionPrefix || this.advancedFiltersActive()); }

  effectiveCollections() {
    let candidates = this.collectionPrefix
      ? this.collections.filter((item) => item.prefix === this.collectionPrefix)
      : [...this.collections];
    const filters = this.filters;
    if (filters.category) candidates = candidates.filter((item) => item.category === filters.category);
    if (filters.palette === "mono") candidates = candidates.filter((item) => !item.palette);
    if (filters.palette === "color") candidates = candidates.filter((item) => item.palette);
    if (filters.style === "color") candidates = candidates.filter((item) => item.palette);
    if (filters.license) candidates = candidates.filter((item) => (item.license?.spdx || item.license?.title || "") === filters.license);
    if (filters.grid) candidates = candidates.filter((item) => Number(item.height) === Number(filters.grid));
    return candidates;
  }

  optionMarkup(values, current, allLabel, label = (value) => value) {
    return `<option value="">${escapeHtml(allLabel)}</option>${values.map((value) => `<option value="${escapeHtml(value)}" ${String(value) === String(current) ? "selected" : ""}>${escapeHtml(label(value))}</option>`).join("")}`;
  }

  async loadCollections() {
    try {
      this.collections = await this.api.collections();
      this.renderSidebar();
      if (this.collectionPrefix) await this.loadCollectionDetails(this.collectionPrefix, true);
    } catch (error) { this.reportError(error); }
  }

  async loadCollectionDetails(prefix, runSearch = true) {
    this.collectionBrowse = null;
    this.renderSidebar();
    if (!prefix) { this.savePreferences(); return; }
    try {
      const browse = await this.api.collection(prefix, { chars: true });
      if (this.collectionPrefix !== prefix) return;
      this.collectionBrowse = browse;
      this.renderSidebar();
      this.savePreferences();
      if (runSearch) this.search();
    } catch (error) { this.reportError(error); }
  }

  async search(query) {
    const input = this.shadowRoot.querySelector('[name="query"]');
    if (query !== undefined) input.value = query;
    const clean = input.value.trim();
    if (clean.length < 2) {
      if (this.collectionPrefix) return this.browseSelectedCollection(clean);
      this.results = []; this.renderResults(); this.setStatus("Enter at least two characters, or choose one collection to browse."); return;
    }
    this.searchController?.abort();
    this.searchController = new AbortController();
    this.loading = true; this.renderResults(); this.setStatus("Searching Iconify…");
    try {
      const candidates = this.effectiveCollections();
      if (!candidates.length) { this.results = []; this.total = 0; this.setStatus("No collections match the active filters."); return; }
      const allCandidates = !this.collectionPrefix && candidates.length === this.collections.length;
      const categoryOnly = allCandidates && this.filters.category && !this.filters.palette && !this.filters.license && !this.filters.grid && this.filters.style !== "color";
      const result = await this.api.search(clean, {
        prefixes: allCandidates ? [] : candidates.map((item) => item.prefix),
        category: categoryOnly ? this.filters.category : "",
        similar: this.filters.similar,
        style: ["fill", "stroke", "mixed"].includes(this.filters.style) ? this.filters.style : "",
        limit: this.limit, start: this.filters.start, signal: this.searchController.signal
      });
      let icons = result.icons || [];
      if (this.filters.iconCategory && this.collectionBrowse) {
        const allowed = new Set(this.collectionBrowse.categories[this.filters.iconCategory] || []);
        icons = icons.filter((name) => allowed.has(iconLabel(name)));
      }
      this.results = icons;
      this.total = Number(result.total) || this.results.length;
      this.setStatus(`${this.results.length} shown${this.total > this.results.length ? ` · ${this.total} matches` : ""}.`);
    } catch (error) { if (error.name !== "AbortError") this.reportError(error); }
    finally { this.loading = false; this.renderResults(); }
  }

  async browseSelectedCollection(query = "") {
    const prefix = this.collectionPrefix;
    if (!prefix) return;
    this.loading = true; this.renderResults(); this.setStatus(`Loading ${prefix}…`);
    try {
      if (!this.effectiveCollections().some((item) => item.prefix === prefix)) {
        this.results = []; this.total = 0; this.setStatus("The selected collection does not match the active collection filters."); return;
      }
      if (!this.collectionBrowse || this.collectionBrowse.prefix !== prefix) this.collectionBrowse = await this.api.collection(prefix, { chars: true });
      let names = this.filters.iconCategory
        ? [...(this.collectionBrowse.categories[this.filters.iconCategory] || [])]
        : [...this.collectionBrowse.icons];
      if (query.length === 1) {
        const character = this.collectionBrowse.chars[query.codePointAt(0).toString(16)];
        names = character ? [character] : [];
      }
      if (this.filters.aliases) names.push(...this.collectionBrowse.aliases);
      if (this.filters.hidden) names.push(...this.collectionBrowse.hidden);
      names = [...new Set(names)].filter(Boolean);
      this.total = names.length;
      this.results = names.slice(this.filters.start, this.filters.start + this.limit).map((name) => `${prefix}:${name}`);
      this.setStatus(`${this.results.length} shown · ${this.total} icons in ${prefix}.`);
    } catch (error) { this.reportError(error); }
    finally { this.loading = false; this.renderResults(); }
  }

  renderDynamic() { this.renderSidebar(); this.renderResults(); this.renderOptions(); this.updateSelection(); }

  renderSidebar() {
    const root = this.shadowRoot;
    if (!root.querySelector(".side-content")) return;
    root.querySelectorAll("[data-tab]").forEach((button) => button.classList.toggle("active", button.dataset.tab === this.activeTab));
    root.querySelector(".filter-marker").classList.toggle("active", this.filtersActive());
    root.querySelector(".favorite-count").textContent = favoriteCount(this.favorites) ? `(${favoriteCount(this.favorites)})` : "";
    const content = root.querySelector(".side-content");
    if (this.activeTab === "favorites") {
      if (!this.favorites.sections.length) { content.innerHTML = '<div class="favorites-empty">Use the ☆ button on any icon to create your first favorites section.</div>'; return; }
      content.innerHTML = this.favorites.sections.map((section) => `<details class="favorite-section" data-section="${escapeHtml(section.id)}"><summary><span>${escapeHtml(section.name)} <small>(${section.icons.length})</small></span><button class="trash icon-button" type="button" title="Delete section" aria-label="Delete ${escapeHtml(section.name)}">${svgIcon("trash")}</button></summary><div class="favorite-icons">${section.icons.map((name) => `<button class="mini" type="button" data-icon="${escapeHtml(name)}" title="${escapeHtml(name)}"><img alt="" src="${this.previewUrl(name)}"><span class="remove" data-remove="${escapeHtml(name)}" aria-label="Remove ${escapeHtml(name)}">${svgIcon("close")}</span></button>`).join("") || '<span class="favorites-empty">Empty</span>'}</div></details>`).join("");
      content.querySelectorAll(".trash").forEach((button) => button.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); const details = button.closest("details"); if (confirm(`Delete the favorites section “${details.querySelector("summary span").textContent.replace(/ \(\d+\)$/, "")}”?`)) { this.favorites = removeFavoriteSection(this.favorites, details.dataset.section); this.saveFavorites(); this.renderDynamic(); } }));
      content.querySelectorAll(".mini").forEach((button) => button.addEventListener("click", (event) => { const details = button.closest("details"); if (event.target.closest(".remove")) { this.favorites = removeFavorite(this.favorites, details.dataset.section, button.dataset.icon); this.saveFavorites(); this.renderDynamic(); } else { this.toggleSelection(button.dataset.icon); } }));
      return;
    }
    const categories = [...new Set(this.collections.map((item) => item.category).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    const licenses = [...new Set(this.collections.map((item) => item.license?.spdx || item.license?.title).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    const grids = [...new Set(this.collections.map((item) => Number(item.height)).filter(Boolean))].sort((a, b) => a - b);
    const iconCategories = this.collectionBrowse && this.collectionBrowse.prefix === this.collectionPrefix ? Object.keys(this.collectionBrowse.categories).sort((a, b) => a.localeCompare(b)) : [];
    content.innerHTML = `
      <div class="field"><label for="collection">Icon collection</label><select id="collection"><option value="">All collections (${this.collections.length})</option>${this.collections.map((item) => `<option value="${escapeHtml(item.prefix)}" ${item.prefix === this.collectionPrefix ? "selected" : ""}>${escapeHtml(item.name)} [${escapeHtml(item.prefix)}] · ${item.total.toLocaleString()}</option>`).join("")}</select></div>
      <p class="filter-help">Collection metadata filters are applied before the Iconify search.</p>
      <div class="field"><label for="collection-category">Collection category</label><select id="collection-category" data-filter="category">${this.optionMarkup(categories, this.filters.category, "All collection categories")}</select></div>
      <div class="field"><label for="palette">Palette</label><select id="palette" data-filter="palette">${this.optionMarkup(["mono", "color"], this.filters.palette, "All palettes", (value) => value === "mono" ? "Monotone" : "Multicolor")}</select></div>
      <div class="field"><label for="icon-style">Icon style</label><select id="icon-style" data-filter="style">${this.optionMarkup(["stroke", "fill", "mixed", "color"], this.filters.style, "All icon styles", (value) => ({ stroke: "Outline / stroke", fill: "Filled / solid", mixed: "Mixed fill + stroke", color: "Multicolor" })[value])}</select></div>
      <div class="field"><label for="license">License</label><select id="license" data-filter="license">${this.optionMarkup(licenses, this.filters.license, "All licenses")}</select></div>
      <div class="field"><label for="grid">Grid</label><select id="grid" data-filter="grid">${this.optionMarkup(grids, this.filters.grid, "All grid sizes", (value) => `${value}px`)}</select></div>
      <div class="field"><label for="icon-category">Icon category</label><select id="icon-category" data-filter="iconCategory" ${iconCategories.length ? "" : "disabled"}>${this.optionMarkup(iconCategories, this.filters.iconCategory, "All icon categories")}</select></div>
      <label class="check"><input type="checkbox" data-check="similar" ${this.filters.similar ? "checked" : ""}> <span>Include similar names</span></label>
      <label class="check"><input type="checkbox" data-check="aliases" ${this.filters.aliases ? "checked" : ""} ${this.collectionPrefix ? "" : "disabled"}> <span>Include aliases when browsing</span></label>
      <label class="check"><input type="checkbox" data-check="hidden" ${this.filters.hidden ? "checked" : ""} ${this.collectionPrefix ? "" : "disabled"}> <span>Include hidden legacy icons</span></label>
      <div class="filter-grid"><div class="field"><label for="result-limit">Result limit</label><input id="result-limit" type="number" min="32" max="999" step="8" value="${this.limit}"></div><div class="field"><label for="start-offset">Start offset</label><input id="start-offset" type="number" min="0" max="${Math.max(0, this.limit - 1)}" step="1" value="${this.filters.start}"></div></div>
      <div class="filter-actions"><button type="button" class="reset-filters" ${this.advancedFiltersActive() ? "" : "disabled"}>Reset filters</button></div>
      <p class="favorites-empty">Collection metadata and licenses are supplied by Iconify.</p>`;
    const rerun = () => { this.savePreferences(); this.renderSidebar(); if (root.querySelector('[name="query"]').value.trim().length >= 2 || this.collectionPrefix) this.search(); };
    content.querySelector("#collection").addEventListener("change", (event) => { this.collectionPrefix = event.target.value; this.filters.iconCategory = ""; this.filters.start = 0; this.savePreferences(); this.loadCollectionDetails(this.collectionPrefix); });
    content.querySelectorAll("[data-filter]").forEach((select) => select.addEventListener("change", (event) => { this.filters[event.target.dataset.filter] = event.target.value; this.filters.start = 0; rerun(); }));
    content.querySelectorAll("[data-check]").forEach((checkbox) => checkbox.addEventListener("change", (event) => { this.filters[event.target.dataset.check] = event.target.checked; rerun(); }));
    content.querySelector("#result-limit").addEventListener("change", (event) => { this.limit = Math.max(32, Math.min(999, Number(event.target.value) || 120)); this.filters.start = Math.min(this.filters.start, Math.max(0, this.limit - 1)); rerun(); });
    content.querySelector("#start-offset").addEventListener("change", (event) => { this.filters.start = Math.max(0, Math.min(this.limit - 1, Number(event.target.value) || 0)); rerun(); });
    content.querySelector(".reset-filters").addEventListener("click", () => { this.filters = normalizeFilters(DEFAULT_FILTERS); rerun(); });
  }

  renderResults() {
    const container = this.shadowRoot.querySelector(".results");
    if (!container) return;
    this.shadowRoot.querySelector(".count").textContent = this.selected.size ? `${this.selected.size} selected` : "";
    if (this.loading) { container.className = "results empty"; container.innerHTML = `<div><div class="empty-icon loading-icon">${svgIcon("loading")}</div><strong>Searching…</strong></div>`; return; }
    if (!this.results.length) { container.className = "results empty"; container.innerHTML = `<div><div class="empty-icon">${svgIcon("search")}</div><strong>Search the Iconify catalog</strong><div>Enter at least two characters to begin.</div></div>`; return; }
    container.className = "results icon-grid";
    container.innerHTML = this.results.map((name) => { const saved = isFavorite(this.favorites, name); return `<button type="button" class="icon-card ${this.selected.has(name) ? "selected" : ""}" data-icon="${escapeHtml(name)}" aria-pressed="${this.selected.has(name)}" title="${escapeHtml(name)}"><span class="star ${saved ? "saved" : ""}" role="button" aria-label="Add ${escapeHtml(name)} to favorites" title="Add to favorites">${svgIcon(saved ? "starSaved" : "star")}</span><img alt="" loading="lazy" src="${this.previewUrl(name)}"><span class="icon-name">${escapeHtml(iconLabel(name))}</span></button>`; }).join("");
    container.querySelectorAll(".icon-card").forEach((card) => card.addEventListener("click", (event) => event.target.closest(".star") ? this.openFavoriteDialog(card.dataset.icon) : this.toggleSelection(card.dataset.icon)));
  }

  renderOptions() {
    const root = this.shadowRoot;
    if (!root.querySelector('[name="size"]')) return;
    root.querySelector('[name="size"]').value = this.size;
    root.querySelector('[name="pngPixels"]').value = this.pngPixels;
    root.querySelector('[name="color"]').value = this.color;
    root.querySelector('[name="zoom"]').value = this.zoom;
    this.applyZoom();
    root.querySelector(".png-option").hidden = this.format !== "png";
    root.querySelectorAll("[data-format]").forEach((button) => button.classList.toggle("active", button.dataset.format === this.format));
  }

  applyZoom() {
    this.style.setProperty("--iap-icon-size", `${this.zoom}px`);
  }

  toggleSelection(name) {
    if (this.selected.has(name)) this.selected.delete(name);
    else { if (!this.multiple) this.selected.clear(); this.selected.add(name); }
    this.updateSelection(); this.renderResults();
  }

  updateSelection() {
    if (!this.shadowRoot.querySelector(".import")) return;
    this.shadowRoot.querySelectorAll(".clear").forEach((button) => button.disabled = !this.selected.size);
    this.shadowRoot.querySelector(".import").disabled = !this.selected.size || this.loading;
    const verb = this.getAttribute("action-label") || "Import";
    this.shadowRoot.querySelector(".import").textContent = this.selected.size ? `${verb} ${this.selected.size}` : `${verb} selected`;
    this.dispatchEvent(new CustomEvent("iconify-selection-change", { bubbles: true, composed: true, detail: { icons: [...this.selected] } }));
  }

  getSelection() { return [...this.selected]; }
  clearSelection() { this.selected.clear(); this.updateSelection(); this.renderResults(); }

  openFavoriteDialog(name) {
    this.favoriteCandidate = name;
    const dialog = this.shadowRoot.querySelector("dialog");
    dialog.querySelector(".dialog-icon").textContent = name;
    dialog.querySelector('[name="favoriteSection"]').innerHTML = this.favorites.sections.length ? this.favorites.sections.map((section) => `<option value="${escapeHtml(section.id)}">${escapeHtml(section.name)}</option>`).join("") : '<option value="">No sections yet</option>';
    dialog.querySelector('[name="newSection"]').value = "";
    dialog.querySelector(".dialog-error").textContent = "";
    dialog.showModal();
  }

  saveFavoriteFromDialog(event) {
    if (event.submitter?.value === "cancel") return;
    event.preventDefault();
    const form = event.currentTarget;
    let sectionId = form.elements.favoriteSection.value;
    const newName = form.elements.newSection.value.trim();
    try {
      if (newName) { const result = createFavoriteSection(this.favorites, newName); this.favorites = result.favorites; sectionId = result.sectionId; }
      if (!sectionId) throw new Error("Select a section or enter a new section name.");
      this.favorites = addFavorite(this.favorites, sectionId, this.favoriteCandidate).favorites;
      this.saveFavorites(); form.closest("dialog").close(); this.renderDynamic();
    } catch (error) { form.querySelector(".dialog-error").textContent = error.message; }
  }

  async importSelected() {
    const names = [...this.selected];
    if (!names.length) return;
    this.loading = true; this.updateSelection(); this.setStatus(`Preparing ${names.length} asset${names.length === 1 ? "" : "s"}…`);
    try {
      const assets = [];
      for (const name of names) {
        const text = sanitizeSvg(await this.api.svg(name, { color: this.color }));
        const blob = this.format === "png" ? await svgToPngBlob(text, this.pngPixels) : new Blob([text], { type: "image/svg+xml" });
        assets.push({ name, format: this.format, mimeType: blob.type, blob, text: this.format === "svg" ? text : undefined, size: this.size, color: this.color, source: "Iconify" });
      }
      this.dispatchEvent(new CustomEvent("iconify-import", { bubbles: true, composed: true, detail: { assets } }));
      this.setStatus(`${assets.length} asset${assets.length === 1 ? "" : "s"} ready for the host application.`);
      if (this.hasAttribute("clear-after-import")) this.clearSelection();
    } catch (error) { this.reportError(error); }
    finally { this.loading = false; this.updateSelection(); this.renderResults(); }
  }

  setStatus(message) { const status = this.shadowRoot.querySelector(".status"); if (status) { status.classList.remove("error"); status.textContent = message; } }
  reportError(error) { const status = this.shadowRoot.querySelector(".status"); if (status) { status.classList.add("error"); status.textContent = error.message; } this.dispatchEvent(new CustomEvent("iconify-error", { bubbles: true, composed: true, detail: { error } })); }
}

if (!customElements.get("iconify-asset-picker")) customElements.define("iconify-asset-picker", IconifyAssetPicker);
