#!/usr/bin/env python3
"""Create an installable zip containing only the Inkscape extension files."""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from icon_importer import __version__  # noqa: E402


FILES = (
    ROOT / "icon_importer.inx",
    ROOT / "icon_importer_extension.py",
    ROOT / "install.cmd",
    ROOT / "uninstall.cmd",
    ROOT / "iconify_search_icon.svg",
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "LICENSE",
)
PACKAGE = ROOT / "icon_importer"
ARCHIVE_NAME = f"inkscape-iconify-search-v{__version__}.zip"


def build(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in FILES:
            archive.write(file_path, file_path.name)
        for file_path in sorted(PACKAGE.rglob("*.py")):
            archive.write(file_path, file_path.relative_to(ROOT))
    return destination


def write_sha256(archive_path: Path) -> Path:
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path.write_text(
        f"{digest}  {archive_path.name}\n",
        encoding="ascii",
    )
    return checksum_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=ROOT / "dist" / ARCHIVE_NAME,
    )
    args = parser.parse_args()
    archive_path = build(args.output.resolve())
    checksum_path = write_sha256(archive_path)
    print(archive_path)
    print(checksum_path)


if __name__ == "__main__":
    main()
