"""Small dependency-free disk cache for API responses and icon SVGs."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path


class DiskCache:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    @classmethod
    def default(cls) -> "DiskCache":
        if os.name == "nt":
            root = Path(
                os.environ.get("LOCALAPPDATA")
                or os.environ.get("TEMP")
                or Path.cwd()
            )
        else:
            root = Path(
                os.environ.get("XDG_CACHE_HOME")
                or (Path.home() / ".cache")
            )
        return cls(root / "InkscapeIconImporter")

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / digest[:2] / f"{digest}.cache"

    def get(self, key: str, max_age_seconds: float) -> bytes | None:
        path = self._path(key)
        try:
            stat = path.stat()
            if max_age_seconds >= 0 and time.time() - stat.st_mtime > max_age_seconds:
                return None
            return path.read_bytes()
        except (FileNotFoundError, OSError):
            return None

    def put(self, key: str, value: bytes) -> None:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(
                f".{os.getpid()}.{threading.get_ident()}.tmp"
            )
            temporary.write_bytes(value)
            os.replace(temporary, path)
        except OSError:
            # Caching must never make an otherwise successful import fail.
            return

    def get_setting(self, key: str, default=None):
        try:
            payload = json.loads(
                (self.directory / "settings.json").read_text(encoding="utf-8")
            )
            return payload.get(key, default) if isinstance(payload, dict) else default
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return default

    def put_setting(self, key: str, value) -> None:
        path = self.directory / "settings.json"
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                current = {}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            current = {}
        current[key] = value
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(
                f".{os.getpid()}.{threading.get_ident()}.tmp"
            )
            temporary.write_text(
                json.dumps(current, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError:
            return
    def prune(self, max_files: int = 800) -> None:
        if max_files < 1 or not self.directory.exists():
            return
        try:
            files = sorted(
                self.directory.glob("*/*.cache"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            for old_file in files[max_files:]:
                old_file.unlink(missing_ok=True)
        except OSError:
            return
