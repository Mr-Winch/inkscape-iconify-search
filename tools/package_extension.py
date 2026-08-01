#!/usr/bin/env python3
"""Create an installable zip containing only the Inkscape extension files."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "icon_importer.inx",
    ROOT / "icon_importer_extension.py",
    ROOT / "install.cmd",
    ROOT / "iconify_search_icon.svg",
    ROOT / "README.md",
    ROOT / "LICENSE",
)
PACKAGE = ROOT / "icon_importer"


def build(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in FILES:
            archive.write(file_path, file_path.name)
        for file_path in sorted(PACKAGE.rglob("*.py")):
            archive.write(file_path, file_path.relative_to(ROOT))
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=ROOT / "dist" / "inkscape-icon-importer.zip",
    )
    args = parser.parse_args()
    print(build(args.output.resolve()))


if __name__ == "__main__":
    main()
