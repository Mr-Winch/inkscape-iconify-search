# Iconify Search for VectorCraft

Iconify Search for VectorCraft is a Windows companion that searches the [Iconify](https://iconify.design/) catalog and places editable SVG artwork directly in the active VectorCraft document.

Current version: **1.0.0**.

## Install

1. Download [Iconify-Search-for-VectorCraft-Setup-1.0.0.exe](https://github.com/Mr-Winch/inkscape-iconify-search/releases/download/vectorcraft-v1.0.0/Iconify-Search-for-VectorCraft-Setup-1.0.0.exe).
2. Run the installer. It creates Start menu and desktop shortcuts.
3. Open **Iconify Search for VectorCraft**.
4. Press **Open VectorCraft** so VectorCraft starts with its local control port enabled.

The installer is self-contained. A newly formatted Windows computer does not need Node.js, Python, Rust, or .NET. To uninstall, use **Settings › Apps › Installed apps › Iconify Search for VectorCraft › Uninstall**.

## How it works

The companion talks only to VectorCraft's documented loopback control protocol on `127.0.0.1:7979`. It sends a sanitized SVG as inline Base64 to the `file.place` command; no temporary artwork file or broad automation folder permission is needed.

If VectorCraft is already running without its control port, close all VectorCraft windows and press **Open VectorCraft** in the companion. The control port is enabled only for that VectorCraft session.

## Features

- Search and browse more than 200 Iconify collections.
- Filter by collection, category, palette, style, license, native grid, icon category, aliases, hidden icons, offset, and result limit.
- Select or deselect individual icons, clear all, and insert several icons at once.
- Multiple icons are arranged into one editable SVG group instead of overlapping in the center of the document.
- Named Favorites sections that start collapsed; remove individual icons or whole sections.
- Persistent favorites, filters, collection, result limit, icon color, import size, format, and preview zoom.
- Light and dark themes. Automatic mode follows VectorCraft when its brightness is reported, then falls back to Windows.
- Monochrome previews use white in dark mode while multicolor collections keep their original colors.
- Iconify API endpoint failover and SVG sanitization.

## Development

```powershell
npm install
npm test
npm start
npm run dist
```

`npm start` opens only the companion. It does not test or modify VectorCraft automatically. `npm run dist` creates the Windows installer in `release/`.

## Compatibility and limitations

- Windows x64.
- Requires a VectorCraft build that supports `--control` and `engine.execute` with `file.place`.
- Catalog search and first-time icon retrieval require internet access.
- Direct placement currently uses SVG. PNG remains visible in the reusable picker but cannot be inserted through this VectorCraft bridge.
- The installer is not code-signed unless a Windows signing certificate is supplied to the build environment, so Windows or third-party antivirus software may show an unknown-publisher warning.

## Licensing

Application code is MIT licensed. Icons and collections have their own licenses, exposed by Iconify; users remain responsible for meeting the selected collection's license.
