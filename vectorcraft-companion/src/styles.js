export const styles = `
:host {
  --iap-bg: #ffffff;
  --iap-panel: #f6f7f9;
  --iap-panel-2: #ffffff;
  --iap-text: #202124;
  --iap-muted: #68707c;
  --iap-border: #d9dde3;
  --iap-accent: #0b67d1;
  --iap-accent-text: #ffffff;
  --iap-danger: #b3261e;
  --iap-focus: #80b7f4;
  --iap-icon-size: 52px;
  color-scheme: light;
  display: block;
  min-width: 280px;
  color: var(--iap-text);
  font: 14px/1.4 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
:host([theme="dark"]), :host([data-resolved-theme="dark"]) {
  --iap-bg: #202124;
  --iap-panel: #292a2d;
  --iap-panel-2: #242528;
  --iap-text: #f1f3f4;
  --iap-muted: #aeb4bc;
  --iap-border: #45484e;
  --iap-accent: #8ab4f8;
  --iap-accent-text: #10233e;
  --iap-danger: #ffb4ab;
  --iap-focus: #8ab4f8;
  color-scheme: dark;
}
* { box-sizing: border-box; }
button, input, select { font: inherit; }
button, select, input[type="search"], input[type="number"], input[type="color"] {
  min-height: 36px; border: 1px solid var(--iap-border); border-radius: 7px;
  background: var(--iap-panel-2); color: var(--iap-text);
}
button { cursor: pointer; padding: 7px 12px; }
svg { display: block; }
.icon-button svg { width: 18px; height: 18px; margin: auto; }
button:hover:not(:disabled) { background: color-mix(in srgb, var(--iap-accent) 12%, var(--iap-panel-2)); }
button:focus-visible, input:focus-visible, select:focus-visible, [tabindex]:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--iap-focus) 45%, transparent); outline-offset: 1px;
}
button:disabled { cursor: default; opacity: .5; }
.app { height: min(760px, 90vh); min-height: 540px; display: grid; grid-template-rows: auto auto 1fr auto; overflow: hidden; background: var(--iap-bg); border: 1px solid var(--iap-border); border-radius: 12px; }
.header { display: flex; align-items: center; gap: 12px; padding: 16px 18px 10px; }
:host([embedded]) .header { display: none; }
:host([embedded]) .app { height: 100%; min-height: 0; border: 0; border-radius: 0; }
.mark { width: 42px; height: 42px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 50%; background: #303238; box-shadow: inset 0 0 0 1px #ffffff30; }
.mark img { width: 38px; height: 38px; display: block; }
.title { font-size: 19px; font-weight: 700; }
.subtitle { color: var(--iap-muted); font-size: 12px; }
.theme { margin-left: auto; width: 38px; padding: 0; font-size: 18px; }
.searchbar { display: grid; grid-template-columns: minmax(100px, 1fr) auto; gap: 8px; padding: 4px 18px 14px; }
.searchbar input { width: 100%; padding: 7px 11px; }
.primary { background: var(--iap-accent); color: var(--iap-accent-text); border-color: var(--iap-accent); font-weight: 600; }
.body { min-height: 0; display: grid; grid-template-columns: 240px minmax(250px, 1fr); border-block: 1px solid var(--iap-border); }
.sidebar { min-height: 0; overflow: auto; border-right: 1px solid var(--iap-border); background: var(--iap-panel-2); }
.tabs { display: grid; grid-template-columns: repeat(2, 1fr); position: sticky; top: 0; z-index: 2; background: var(--iap-panel-2); border-bottom: 1px solid var(--iap-border); }
.tab { border: 0; border-radius: 0; background: transparent; color: var(--iap-muted); }
.tab.active { color: var(--iap-text); box-shadow: inset 0 -3px var(--iap-accent); font-weight: 700; }
.filter-marker { display: none; }
.filter-marker.active { display: inline-block; width: 7px; height: 7px; margin-left: 3px; border-radius: 50%; background: var(--iap-accent); vertical-align: middle; }
.side-content { padding: 14px; }
.field { display: grid; gap: 6px; margin-bottom: 13px; }
.field label, .legend { color: var(--iap-muted); font-size: 12px; font-weight: 600; }
.field select, .field input { width: 100%; padding: 6px 8px; }
.check { display: flex; align-items: flex-start; gap: 8px; margin: 9px 0; font-size: 12px; }
.check input { margin: 2px 0 0; accent-color: var(--iap-accent); }
.filter-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.filter-grid .field { margin: 0; }
.filter-actions { display: flex; justify-content: flex-end; padding-top: 5px; border-top: 1px solid var(--iap-border); margin-top: 13px; }
.filter-help { color: var(--iap-muted); font-size: 11px; margin: -3px 0 12px; }
.favorites-empty, .empty, .status { color: var(--iap-muted); }
.favorite-section { border: 1px solid var(--iap-border); border-radius: 8px; margin-bottom: 9px; overflow: hidden; background: var(--iap-panel); }
.favorite-section summary { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 5px; cursor: pointer; padding: 9px 8px 9px 11px; font-weight: 650; }
.favorite-section summary::marker { color: var(--iap-muted); }
.trash { min-height: 28px; width: 30px; border: 0; padding: 0; color: var(--iap-danger); background: transparent; }
.favorite-icons { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 5px; padding: 0 8px 8px; }
.mini { position: relative; aspect-ratio: 1; border: 1px solid var(--iap-border); border-radius: 7px; display: grid; place-items: center; background: var(--iap-panel-2); }
.mini img { width: 60%; height: 60%; }
.remove { position: absolute; right: 1px; top: 1px; min-height: 20px; width: 20px; padding: 0; border: 0; border-radius: 50%; color: var(--iap-danger); background: var(--iap-panel-2); line-height: 1; }
.main { min-width: 0; min-height: 0; display: grid; grid-template-rows: auto 1fr auto; }
.toolbar { display: flex; align-items: center; min-height: 49px; gap: 10px; padding: 8px 14px; border-bottom: 1px solid var(--iap-border); }
.toolbar strong { font-size: 15px; }
.count { color: var(--iap-muted); font-size: 12px; }
.toolbar .spacer { flex: 1; }
.zoom-control { display: flex; align-items: center; gap: 8px; color: var(--iap-muted); font-size: 11px; }
.zoom-control input { width: 104px; min-height: 24px; accent-color: var(--iap-accent); }
.clear { min-height: 32px; padding-block: 5px; }
.grid-wrap { min-height: 0; overflow: auto; padding: 12px; }
.icon-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(calc(var(--iap-icon-size) + 32px), 1fr)); gap: 6px; align-content: start; }
.icon-card { position: relative; min-width: 0; height: calc(var(--iap-icon-size) + 54px); padding: 8px 5px 5px; display: grid; grid-template-rows: 1fr auto; place-items: center; gap: 4px; background: var(--iap-panel-2); }
.icon-card.selected { border-color: var(--iap-accent); box-shadow: inset 0 0 0 2px var(--iap-accent); }
.icon-card img { width: var(--iap-icon-size); height: var(--iap-icon-size); object-fit: contain; }
.icon-name { width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; color: var(--iap-muted); text-align: center; }
.star { position: absolute; right: 2px; top: 2px; z-index: 1; min-height: 25px; width: 27px; padding: 4px; border: 0; background: transparent; color: var(--iap-muted); }
.star svg { width: 17px; height: 17px; }
.star.saved { color: #e5a50a; }
.empty { height: 100%; display: grid; place-content: center; text-align: center; padding: 25px; }
.empty-icon { width: 38px; height: 38px; margin: 0 auto 8px; }
.empty-icon svg { width: 100%; height: 100%; }
.loading-icon { animation: iap-spin .9s linear infinite; }
.status { min-height: 31px; padding: 7px 14px; font-size: 12px; border-top: 1px solid var(--iap-border); }
.footer { display: grid; grid-template-columns: 1fr auto; align-items: end; gap: 16px; padding: 12px 16px; background: var(--iap-panel-2); }
.options { display: flex; flex-wrap: wrap; align-items: end; gap: 10px; }
.compact { display: grid; gap: 4px; }
.compact label { font-size: 11px; color: var(--iap-muted); }
.compact input, .compact select { width: 92px; padding: 5px 7px; }
.format { display: flex; border: 1px solid var(--iap-border); border-radius: 7px; overflow: hidden; }
.format button { border: 0; border-radius: 0; min-height: 34px; padding: 5px 10px; }
.format button.active { background: var(--iap-accent); color: var(--iap-accent-text); }
.actions { display: flex; gap: 8px; }
dialog { width: min(390px, calc(100% - 30px)); border: 1px solid var(--iap-border); border-radius: 11px; padding: 0; color: var(--iap-text); background: var(--iap-bg); box-shadow: 0 18px 55px #0006; }
dialog::backdrop { background: #0007; }
.dialog-content { padding: 18px; }
.dialog-content h2 { margin: 0 0 5px; font-size: 18px; }
.dialog-content p { margin: 0 0 16px; color: var(--iap-muted); }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.error { color: var(--iap-danger); }
@keyframes iap-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .loading-icon { animation: none; } }
@media (max-width: 680px) {
  .app { height: 90vh; }
  .body { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid var(--iap-border); max-height: 210px; }
  .footer { grid-template-columns: 1fr; }
  .actions { justify-content: flex-end; }
}
`;
