"""Client for Iconify's public icon search, catalog, and SVG APIs."""

from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable

from .cache import DiskCache
from .models import (
    CollectionBrowseResult,
    CollectionInfo,
    IconInfo,
    SearchResult,
)


ICON_NAME_RE = re.compile(
    r"^(?P<prefix>[a-z0-9]+(?:-[a-z0-9]+)*):"
    r"(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
PREFIX_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-?$")


class IconifyError(RuntimeError):
    """Raised when Iconify cannot return a valid response."""


class IconifyClient:
    DEFAULT_BASE_URLS = (
        "https://api.iconify.design",
        "https://api.simplesvg.com",
        "https://api.unisvg.com",
    )
    SEARCH_CACHE_SECONDS = 15 * 60
    CATALOG_CACHE_SECONDS = 24 * 60 * 60
    SVG_CACHE_SECONDS = 30 * 24 * 60 * 60
    MAX_RESPONSE_BYTES = 2_000_000

    def __init__(
        self,
        cache: DiskCache | None = None,
        timeout: float = 10.0,
        base_urls: Iterable[str] | None = None,
    ):
        self.cache = cache
        self.timeout = timeout
        self.base_urls = tuple(base_urls or self.DEFAULT_BASE_URLS)
        self._windows_context: ssl.SSLContext | None = None
        self._windows_context_attempted = False

    def list_collections(
        self, prefixes: Iterable[str] | None = None
    ) -> tuple[CollectionInfo, ...]:
        params: dict[str, str] = {}
        clean_prefixes = self._validate_prefixes(prefixes)
        if clean_prefixes:
            params["prefixes"] = ",".join(clean_prefixes)
        payload = self._request_json(
            "/collections", params, self.CATALOG_CACHE_SECONDS
        )
        if not isinstance(payload, dict):
            raise IconifyError("Iconify returned invalid collection data.")
        collections = [
            CollectionInfo.from_api(prefix, info)
            for prefix, info in payload.items()
            if PREFIX_RE.fullmatch(str(prefix)) and isinstance(info, dict)
        ]
        return tuple(sorted(collections, key=lambda item: (item.name.casefold(), item.prefix)))

    def browse_collection(
        self, prefix: str, include_chars: bool = True
    ) -> CollectionBrowseResult:
        self._validate_prefix(prefix)
        payload = self._request_json(
            "/collection",
            {
                "prefix": prefix,
                "info": "true",
                "chars": "true" if include_chars else "false",
            },
            self.CATALOG_CACHE_SECONDS,
        )
        categories = {
            str(name): tuple(dict.fromkeys(str(icon) for icon in icons))
            for name, icons in (payload.get("categories") or {}).items()
            if isinstance(icons, list)
        }
        uncategorized = tuple(
            dict.fromkeys(str(icon) for icon in (payload.get("uncategorized") or ()))
        )
        visible: list[str] = list(uncategorized)
        for icons in categories.values():
            visible.extend(icons)
        visible = list(dict.fromkeys(visible))
        return CollectionBrowseResult(
            prefix=prefix,
            total=int(payload.get("total") or len(visible)),
            icons=tuple(visible),
            categories=categories,
            aliases={
                str(name): str(parent)
                for name, parent in (payload.get("aliases") or {}).items()
            },
            hidden=tuple(str(item) for item in (payload.get("hidden") or ())),
            chars={
                str(char): str(name)
                for char, name in (payload.get("chars") or {}).items()
            },
        )

    def suggest_keywords(self, text: str, contains: bool = False) -> tuple[str, ...]:
        keyword = text.strip().lower()
        if len(keyword) < 2:
            return ()
        parameter = "keyword" if contains else "prefix"
        payload = self._request_json(
            "/keywords",
            {parameter: keyword},
            self.SEARCH_CACHE_SECONDS,
        )
        if payload.get("invalid"):
            return ()
        return tuple(str(item) for item in (payload.get("matches") or ()))

    def search(
        self,
        query: str,
        prefix: str | None = None,
        limit: int = 64,
        start: int = 0,
        *,
        prefixes: Iterable[str] | None = None,
        category: str | None = None,
        similar: bool = True,
        style: str | None = None,
    ) -> SearchResult:
        clean_query = " ".join(query.split())
        if len(clean_query) < 2:
            return SearchResult(icons=(), total=0, start=0, limit=limit)

        result_limit = max(32, min(int(limit), 999))
        result_start = max(0, int(start))
        if result_start >= result_limit:
            raise ValueError("Result start must be smaller than the result limit.")
        params: dict[str, str | int] = {
            "query": clean_query,
            "limit": result_limit,
            "start": result_start,
        }

        selected_prefixes = self._validate_prefixes(prefixes)
        if selected_prefixes:
            params["prefixes"] = ",".join(selected_prefixes)
        elif prefix:
            self._validate_prefix(prefix)
            params["prefix"] = prefix
        if category:
            params["category"] = category
        if not similar:
            params["similar"] = "false"
        if style:
            if style not in {"fill", "stroke"}:
                raise ValueError("Style must be 'fill' or 'stroke'.")
            # Supported by Iconify API deployments that enable style indexing.
            params["style"] = style

        payload = self._request_json(
            "/search", params, self.SEARCH_CACHE_SECONDS
        )
        collection_payloads = payload.get("collections") or {}
        collections = {
            item_prefix: CollectionInfo.from_api(item_prefix, item_payload)
            for item_prefix, item_payload in collection_payloads.items()
        }
        icons: list[IconInfo] = []
        for full_name in payload.get("icons") or ():
            match = ICON_NAME_RE.fullmatch(str(full_name))
            if not match:
                continue
            item_prefix = match.group("prefix")
            collection = collections.get(
                item_prefix,
                CollectionInfo(prefix=item_prefix, name=item_prefix),
            )
            icons.append(
                IconInfo(
                    full_name=str(full_name),
                    prefix=item_prefix,
                    name=match.group("name"),
                    collection=collection,
                )
            )
        return SearchResult(
            icons=tuple(icons),
            total=int(payload.get("total") or len(icons)),
            start=int(payload.get("start") or 0),
            limit=int(payload.get("limit") or result_limit),
            collections=collections,
        )

    def fetch_svg(self, full_name: str, color: str | None = None) -> bytes:
        match = self._icon_match(full_name)
        params = {"color": color} if color else {}
        return self._request(
            f"/{match.group('prefix')}/{match.group('name')}.svg",
            params,
            cache_seconds=self.SVG_CACHE_SECONDS,
        )

    def fetch_thumbnail(
        self, full_name: str, size: int = 64, color: str | None = "#343a40"
    ) -> bytes:
        match = self._icon_match(full_name)
        pixels = max(16, min(int(size), 256))
        params: dict[str, str | int] = {"width": pixels, "height": pixels}
        if color:
            params["color"] = color
        return self._request(
            f"/{match.group('prefix')}/{match.group('name')}.svg",
            params,
            cache_seconds=self.SVG_CACHE_SECONDS,
        )

    @staticmethod
    def _icon_match(full_name: str) -> re.Match:
        match = ICON_NAME_RE.fullmatch(full_name)
        if not match:
            raise ValueError(f"Invalid Iconify icon name: {full_name!r}")
        return match

    @staticmethod
    def _validate_prefix(prefix: str) -> None:
        if not PREFIX_RE.fullmatch(prefix):
            raise ValueError(f"Invalid icon collection prefix: {prefix!r}")

    def _validate_prefixes(
        self, prefixes: Iterable[str] | None
    ) -> tuple[str, ...]:
        clean = tuple(dict.fromkeys(str(item) for item in (prefixes or ()) if item))
        for prefix in clean:
            self._validate_prefix(prefix)
        return clean

    def _request_json(
        self,
        path: str,
        params: dict[str, str | int],
        cache_seconds: float,
    ) -> dict:
        raw = self._request(path, params, cache_seconds)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IconifyError("Iconify returned invalid JSON data.") from exc
        if not isinstance(payload, dict):
            raise IconifyError("Iconify returned an unexpected response.")
        return payload

    def _request(
        self,
        path: str,
        params: dict[str, str | int],
        cache_seconds: float,
    ) -> bytes:
        query = urllib.parse.urlencode(params)
        cache_key = f"{path}?{query}"
        if self.cache:
            cached = self.cache.get(cache_key, cache_seconds)
            if cached is not None:
                return cached

        errors: list[str] = []
        for base_url in self.base_urls:
            url = f"{base_url.rstrip('/')}{path}"
            if query:
                url += f"?{query}"
            try:
                data = self._download(url)
                if self.cache:
                    self.cache.put(cache_key, data)
                return data
            except (IconifyError, OSError, urllib.error.URLError) as exc:
                errors.append(f"{base_url}: {exc}")
        detail = "\n".join(errors)
        raise IconifyError(
            "Could not connect securely to the Iconify API. "
            "Check your internet connection."
            + (f"\n\n{detail}" if detail else "")
        )

    def _download(self, url: str) -> bytes:
        try:
            return self._urllib_download(url)
        except urllib.error.URLError as primary_error:
            if not self._is_certificate_error(primary_error):
                raise

            context = self._get_windows_trust_context()
            if context is not None:
                try:
                    return self._urllib_download(url, context=context)
                except urllib.error.URLError:
                    pass

            try:
                return self._curl_download(url)
            except OSError as curl_error:
                raise OSError(
                    "TLS certificate verification failed in Inkscape's Python, "
                    "and the secure Windows certificate fallback also failed. "
                    f"Python: {primary_error}; Windows cURL: {curl_error}"
                ) from curl_error

    def _urllib_download(
        self, url: str, context: ssl.SSLContext | None = None
    ) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json,image/svg+xml;q=0.9,*/*;q=0.1",
                "User-Agent": "Inkscape-Icon-Importer/0.2",
            },
        )
        kwargs = {"timeout": self.timeout}
        if context is not None:
            kwargs["context"] = context
        with urllib.request.urlopen(request, **kwargs) as response:
            data = response.read(self.MAX_RESPONSE_BYTES + 1)
        return self._validate_download_size(data)

    def _curl_download(self, url: str) -> bytes:
        executable = shutil.which("curl.exe") or shutil.which("curl")
        if not executable:
            raise OSError("Windows cURL was not found.")
        creation_flags = 0x08000000 if os.name == "nt" else 0
        result = subprocess.run(
            [
                executable,
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--proto",
                "=https",
                "--tlsv1.2",
                "--max-time",
                str(max(1, round(self.timeout))),
                "--header",
                "User-Agent: Inkscape-Icon-Importer/0.2",
                url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout + 3,
            check=False,
            creationflags=creation_flags,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise OSError(detail or f"cURL exited with code {result.returncode}.")
        return self._validate_download_size(result.stdout)

    def _get_windows_trust_context(self) -> ssl.SSLContext | None:
        if self._windows_context_attempted:
            return self._windows_context
        self._windows_context_attempted = True
        if os.name != "nt":
            return None
        try:
            certificates: list[bytes] = []
            enum_certificates = getattr(ssl, "enum_certificates", None)
            if callable(enum_certificates):
                for store_name in ("ROOT", "CA"):
                    certificates.extend(
                        certificate
                        for certificate, encoding, _trust
                        in enum_certificates(store_name)
                        if encoding == "x509_asn"
                    )
            else:
                certificates.extend(self._windows_certificates_via_cryptoapi())
            if not certificates:
                return None
            context = ssl.create_default_context()
            context.load_verify_locations(cadata="".join(
                ssl.DER_cert_to_PEM_cert(certificate)
                for certificate in certificates
            ))
            self._windows_context = context
        except (AttributeError, OSError, ValueError, ssl.SSLError):
            self._windows_context = None
        return self._windows_context

    @staticmethod
    def _windows_certificates_via_cryptoapi() -> tuple[bytes, ...]:
        """Read trusted certificates when MinGW Python lacks ssl.enum_certificates."""
        import ctypes

        class CertContext(ctypes.Structure):
            _fields_ = [
                ("encoding_type", ctypes.c_uint32),
                ("encoded", ctypes.POINTER(ctypes.c_ubyte)),
                ("encoded_size", ctypes.c_uint32),
                ("cert_info", ctypes.c_void_p),
                ("cert_store", ctypes.c_void_p),
            ]

        context_pointer = ctypes.POINTER(CertContext)
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        crypt32.CertOpenSystemStoreW.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p
        ]
        crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p
        crypt32.CertEnumCertificatesInStore.argtypes = [
            ctypes.c_void_p, context_pointer
        ]
        crypt32.CertEnumCertificatesInStore.restype = context_pointer
        crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        crypt32.CertCloseStore.restype = ctypes.c_bool

        certificates: list[bytes] = []
        for store_name in ("ROOT", "CA"):
            store = crypt32.CertOpenSystemStoreW(None, store_name)
            if not store:
                continue
            try:
                previous = context_pointer()
                while True:
                    current = crypt32.CertEnumCertificatesInStore(
                        store, previous
                    )
                    if not current:
                        break
                    certificates.append(ctypes.string_at(
                        current.contents.encoded,
                        current.contents.encoded_size,
                    ))
                    previous = current
            finally:
                crypt32.CertCloseStore(store, 0)
        return tuple(certificates)

    def _validate_download_size(self, data: bytes) -> bytes:
        if len(data) > self.MAX_RESPONSE_BYTES:
            raise IconifyError("Iconify response exceeded the 2 MB safety limit.")
        return data

    @staticmethod
    def _is_certificate_error(error: BaseException) -> bool:
        current: BaseException | None = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            text = str(current).upper()
            if "CERTIFICATE_VERIFY_FAILED" in text or "CERTIFICATE VERIFY FAILED" in text:
                return True
            reason = getattr(current, "reason", None)
            current = reason if isinstance(reason, BaseException) else current.__cause__
        return False
