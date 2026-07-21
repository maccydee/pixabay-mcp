"""Download-to-server library with a JSON manifest.

Pixabay forbids hotlinking, so assets are fetched to <data_dir>/library/ before
use. The manifest records provenance + attribution and dedups by (hit id, size).
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import projections
from .client import PixabayError

_USER_AGENT = "pixabay-mcp/1.0 (+https://modelcontextprotocol.io)"


class Library:
    def __init__(self, library_dir: Path, manifest_path: Path) -> None:
        self.dir = Path(library_dir)
        self.manifest_path = Path(manifest_path)
        self.dir.mkdir(parents=True, exist_ok=True)

    # ---- manifest -----------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            return {}
        try:
            return json.loads(self.manifest_path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self, manifest: Dict[str, Any]) -> None:
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=2), "utf-8")
        os.replace(tmp, self.manifest_path)

    # ---- operations ---------------------------------------------------------

    def download(self, hit: Dict[str, Any], size: str, url: str, kind: str) -> Dict[str, Any]:
        entry_id = f"{hit.get('id')}-{size}"
        manifest = self._load()
        if entry_id in manifest and Path(manifest[entry_id]["path"]).exists():
            return {**manifest[entry_id], "deduped": True}

        ext = self._extension(url)
        path = self.dir / f"{entry_id}{ext}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp, open(path, "wb") as fh:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()
                fh.write(data)
        except (urllib.error.URLError, OSError) as exc:
            raise PixabayError(f"Failed to download asset: {exc}") from exc

        record = {
            "entry_id": entry_id,
            "hit_id": hit.get("id"),
            "kind": kind,
            "size": size,
            "path": str(path),
            "bytes": len(data),
            "content_type": content_type,
            "source_url": url,
            "by": hit.get("user"),
            "page_url": hit.get("pageURL"),
            "attribution": projections.attribution(hit),
            "attribution_notice": projections.attribution_notice(hit),
            "downloaded_at": time.time(),
        }
        manifest[entry_id] = record
        self._save(manifest)
        return {**record, "deduped": False}

    def list(self) -> List[Dict[str, Any]]:
        manifest = self._load()
        return [
            {
                "entry_id": r["entry_id"],
                "kind": r.get("kind"),
                "size": r.get("size"),
                "path": r.get("path"),
                "bytes": r.get("bytes"),
                "by": r.get("by"),
                "attribution": r.get("attribution"),
            }
            for r in manifest.values()
        ]

    def remove(self, entry_id: str) -> Dict[str, Any]:
        manifest = self._load()
        record = manifest.pop(entry_id, None)
        if record is None:
            return {"removed": False, "reason": f"no library entry '{entry_id}'"}
        try:
            Path(record["path"]).unlink()
        except OSError:
            pass
        self._save(manifest)
        return {"removed": True, "entry_id": entry_id, "path": record.get("path")}

    def count(self) -> int:
        return len(self._load())

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _extension(url: str) -> str:
        path = urlparse(url).path
        _, ext = os.path.splitext(path)
        if ext:
            return ext
        guessed = mimetypes.guess_extension(mimetypes.guess_type(url)[0] or "") or ""
        return guessed or ".bin"
