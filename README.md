# Inkscape Icon Importer

Search Iconify's open-source icon catalog and insert an icon directly into the
current Inkscape document as editable SVG or embedded PNG.

## Features

- Loads the complete collection catalog dynamically from Iconify (231 collections
  at the time of this release; the count updates automatically)
- Search all collections or any combination of selected collections
- Click icons to select or unselect them, then import the selection as an arranged grid
- Filter by collection category, palette, license, grid size, icon style, and a
  collection's own icon categories
- Iconify keyword suggestions, similar-name matching, result limit, start offset,
  collection browsing, aliases, hidden legacy icons, and character lookup
- Polished native GTK interface with persistent light and dark themes
- Live icon-grid zoom from 32–128 px
- Compact SVG/PNG controls, import size, PNG resolution, color, and stroke scaling
- Persistent icon color, import size, result limit, zoom, filters, and collection selection
- Filters open by default and show a marker in the tab whenever any filter is active
- Editable SVG import into the current layer or self-contained base64 PNG import
- Source and license details before import and metadata on the imported object
- SVG sanitization and namespaced resource IDs to prevent document collisions
- Local response/thumbnail cache
- No third-party Python packages beyond those bundled with Inkscape

## Requirements

- Inkscape 1.2 or newer
- Internet access while retrieving uncached icons
- An official Inkscape build with `inkex`, GTK 3, and SVG thumbnail support
  through GdkPixbuf/librsvg

PNG import starts a short-lived Inkscape process to rasterize the selected SVG.
SVG import does not start another process.

## Install on Windows

1. Extract `inkscape-icon-importer.zip` completely.
2. Double-click `install.cmd`.
3. Close every Inkscape window and reopen Inkscape.
4. Choose **Extensions → Import/Export → Search and Import Icons**.

The installer copies the extension to:

```text
%APPDATA%\inkscape\extensions\icon-importer
```

Rerun `install.cmd` to upgrade an existing installation; it overwrites the old
extension files while retaining the cache.

## Manual installation

1. In Inkscape, open **Edit → Preferences → System** and locate **User
   extensions**.
2. Copy `icon_importer.inx`, `icon_importer_extension.py`,
   `iconify_search_icon.svg`, and the complete `icon_importer` folder into that
   directory.
3. Restart Inkscape.

## Usage

Type at least two characters to search. To browse without a search term, clear
the search box and select exactly one collection. Use the left panel to choose
collections and filters; selecting one collection also enables its collection-
specific icon categories when available. Click an icon to select it; click it again
to unselect it. **Clear selection** deselects everything. Selected icons are
imported together in a centered, non-overlapping grid.

The SVG/PNG switch controls the import type:

- **SVG** inserts editable vector elements, grouped and centered in the current
  view.
- **PNG** inserts a self-contained raster image. Display size and raster
  resolution are independent.

Monochrome icons use the selected color by default. The theme, icon color,
import size, result limit, zoom, active filters, and selected collections are
remembered even after Inkscape is closed. Enable **Preserve original colors**
for multicolor icons. Every collection retains its own license; Iconify
does not replace the source collection's license.

## TLS and networking

Some Inkscape Windows builds cannot see the operating system certificate store,
which can produce `CERTIFICATE_VERIFY_FAILED` even when Iconify opens normally in
a browser. The extension now tries, in order:

1. Inkscape Python's verified HTTPS connection
2. A verified TLS context populated from the Windows certificate stores
3. Windows `curl.exe` with HTTPS-only, TLS 1.2-or-newer verification

Certificate verification is never disabled. Search terms and selected icon names
are sent to Iconify's public API. Search responses are cached for 15 minutes;
SVGs and thumbnails are cached for 30 days. No account or API key is required.

## Development

Run the standard-library tests and build the installable ZIP with:

```powershell
$env:ICON_IMPORTER_TEST_TMP = 'C:\tmp'
python -m unittest discover -s tests -v
python tools/package_extension.py
```

The GTK/Inkscape integration must be exercised inside an Inkscape extension
environment. The project deliberately runs against the `inkex` version bundled
with Inkscape.

## License

The extension source is licensed under the MIT License. Imported icons remain
subject to their respective collection licenses, displayed before import.