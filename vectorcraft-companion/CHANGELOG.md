# Changelog

## 1.0.0 — 2026-10-27

- Created a self-contained Windows companion for VectorCraft.
- Added direct SVG placement through VectorCraft's documented loopback control protocol.
- Added VectorCraft launching, connection diagnostics, and theme synchronization with Windows fallback.
- Added non-overlapping composition for multiple selected icons.
- Added persistent preview zoom and adapted the complete Iconify picker, filters, and grouped favorites.
- Fixed missing result thumbnails by loading, sanitizing, and caching SVG previews through the same resilient Iconify API connection used by search.
- Added an assisted NSIS installer with desktop and Start menu shortcuts and standard Windows uninstallation.
- Added protocol composition and package-integrity tests.

## Component history

## Asset Picker 1.0.0 — 2026-08-24

- Promoted the complete reusable picker to its first stable public version.
- Aligned the package, component UI, demo, documentation, archive name, and changelog on version 1.0.0.
- Added a reproducible release packager with SHA-256 and npm integrity metadata.
- Added automated tests for release identity and package contents.
- Added GitHub Actions validation for tests, package creation, and checksum verification.
- Documented direct package installation, vendoring, updating, and removal.

## 0.2.0 — 2026-08-14

- Added collection category, palette, style, license, grid, and icon-category filters.
- Added similar-name, alias, hidden legacy, result-limit, and start-offset controls.
- Added collection browsing without requiring a search query.
- Persisted the complete filter state and active collection.
- Added an active-filter marker.
- Integrated the supplied Iconify Search identity icon as the component logo and favicon.
- Changed monotone previews to white in dark mode while preserving multicolor previews.

## 0.1.0 — 2026-08-14

- Initial public release.
