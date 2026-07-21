"""24-hour disk cache keyed independently of pagination.

The key is a hash of the endpoint + normalized query (minus page/per_page), so
re-running the same search reuses the cached hits and paging is free. Entries
expire 24h after their FIRST fetch (Pixabay's caching requirement), regardless
of later page appends.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def result_id(endpoint: str, params: Dict[str, Any]) -> str:
    """Stable id for a search, independent of page/per_page."""
    material = {k: v for k, v in params.items() if k not in ("page", "per_page")}
    blob = endpoint + "|" + json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


class DiskCache:
    def __init__(self, cache_dir: Path, ttl_seconds: int) -> None:
        self.dir = Path(cache_dir)
        self.ttl = ttl_seconds
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        if time.time() - entry.get("created", 0) > self.ttl:
            self._unlink(path)
            return None
        return entry

    def set(self, key: str, entry: Dict[str, Any]) -> None:
        entry = dict(entry)
        entry.setdefault("created", time.time())  # preserve original fetch time
        tmp = self._path(key).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entry), "utf-8")
        os.replace(tmp, self._path(key))

    def keys(self) -> List[str]:
        return [p.stem for p in self.dir.glob("*.json")]

    def purge_expired(self) -> int:
        removed = 0
        now = time.time()
        for path in self.dir.glob("*.json"):
            try:
                created = json.loads(path.read_text("utf-8")).get("created", 0)
            except (OSError, ValueError):
                created = 0
            if now - created > self.ttl:
                self._unlink(path)
                removed += 1
        return removed

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink()
        except OSError:
            pass
