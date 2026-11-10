"""Cached, mirror-aware HTTP downloads."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

from uap_geo.common.config import SourceConfig

log = logging.getLogger(__name__)

USER_AGENT = "uap-geo/0.1 (research; github.com/Fagundo/uap-geo)"


class DownloadError(RuntimeError):
    pass


def filename_from_url(url: str) -> str:
    """Pick a sensible local file name: `?name=` if present, else the last path segment."""
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    query_name = parse_qs(parsed.query).get("name")
    if query_name:
        return query_name[0]
    tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return tail or "download"


class Downloader:
    """Downloads files into a cache directory and skips files already present."""

    def __init__(self, cache_dir: Path, timeout: int = 300) -> None:
        self._cache_dir = cache_dir
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT

    def fetch(self, source: SourceConfig, filename: str, url_index: int | None = None) -> Path:
        """Fetch a source's file, trying each mirror URL in turn (or one URL by index)."""
        target = self._cache_dir / source.name / filename
        if target.exists() and target.stat().st_size > 0:
            return target
        urls = source.urls if url_index is None else (source.urls[url_index],)
        errors: list[str] = []
        for url in urls:
            try:
                self._stream(url, target)
                return target
            except (requests.RequestException, DownloadError) as exc:
                errors.append(f"{url}: {exc}")
                log.warning("Download failed for %s: %s", url, exc)
        raise DownloadError(f"All URLs failed for '{source.name}':\n" + "\n".join(errors))

    def fetch_url(self, source_name: str, url: str, filename: str, params: dict[str, Any] | None = None) -> Path:
        """Fetch one URL (e.g. a paged API query) into the source's cache folder."""
        target = self._cache_dir / source_name / filename
        if target.exists() and target.stat().st_size > 0:
            return target
        self._stream(url, target, params=params)
        return target

    def _stream(self, url: str, target: Path, params: dict[str, Any] | None = None) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        log.info("Downloading %s", url)
        with self._session.get(url, params=params, stream=True, timeout=self._timeout) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
        if tmp.stat().st_size == 0:
            tmp.unlink()
            raise DownloadError("empty response")
        tmp.replace(target)
