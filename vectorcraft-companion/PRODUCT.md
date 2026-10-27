# Iconify Search for VectorCraft

## Product facts

- **Platform:** Windows desktop companion for VectorCraft.
- **Primary job:** Search the Iconify catalog, organize favorite icons, select one or more icons, and place them as editable SVG artwork in the active VectorCraft document.
- **Integration:** Uses VectorCraft's documented loopback control protocol. VectorCraft must be started with `--control 7979`; the companion can start it that way.
- **Distribution:** A self-contained Windows installer. End users should not need Node.js, Python, Rust, or .NET.
- **Identity:** Uses the existing Iconify Search icon and the established picker interaction model shared by the Inkscape and Office editions.
- **Theme:** Follows VectorCraft's reported brightness when available, otherwise the Windows theme. A manual light/dark override remains available.
- **Persistence:** Search filters, selected collections, zoom, import size, color, format, result limit, theme preference, and favorites persist between sessions.
- **Offline boundary:** Catalog search and icon retrieval require internet access. Saved favorites keep their names, but their artwork also requires Iconify unless cached by the web runtime.

## Inferred decisions

These decisions are inferred from the existing project history and the current VectorCraft integration discussion.

- The first release is a companion application, not an internal VectorCraft panel plug-in, because the public plug-in surface does not yet provide a stable in-app panel/network workflow for this product.
- SVG is the default and recommended format. PNG remains available for parity with the reusable picker, although SVG provides the best editing experience in VectorCraft.
- Multiple selected icons are placed as one imported SVG composition so they arrive visibly arranged instead of overlapping at the center of the document.
- The companion does not close or restart VectorCraft automatically. If VectorCraft is already running without its control port, the UI explains that it must be closed and reopened through the companion.

## Experience brief

The interface should feel like a compact VectorCraft utility: dense, calm, immediately legible, and native to a professional vector workflow. Search is the dominant action. Filters and Favorites share the left rail, results occupy the flexible center, and insertion settings stay together near the final action. Connection state must always be visible without dominating the catalog.

The established yellow Iconify Search mark is the signature accent. It is used for identity and connection success; normal controls use the current VectorCraft/Windows theme palette. Dark mode previews monochrome icons in white for visibility while preserving multicolor icons.
