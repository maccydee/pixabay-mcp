"""Search orchestration: cache-backed, free pagination.

A search fetches one API page (API_PAGE_SIZE hits), caches the raw hits under a
page-independent result_id, and hands back a SLICE_SIZE window of slim hits.
paginate() walks the cached window for free, only hitting the API again when the
cursor runs past what's cached and more hits exist server-side.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from . import projections
from .cache import DiskCache, result_id
from .client import IMAGE_ENDPOINT, PixabayClient, VIDEO_ENDPOINT
from .config import API_PAGE_SIZE, SLICE_SIZE

_SLIMMERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "image": projections.slim_image,
    "video": projections.slim_video,
}


class ResultExpired(RuntimeError):
    """The result_id is unknown or its 24h cache entry has expired."""


class SearchService:
    def __init__(self, client: PixabayClient, cache: DiskCache) -> None:
        self.client = client
        self.cache = cache
        self._cursors: Dict[str, int] = {}  # result_id -> next offset (in-memory)

    # ---- public API ---------------------------------------------------------

    def search(self, kind: str, params: Dict[str, Any], full_tags: bool) -> Dict[str, Any]:
        endpoint = IMAGE_ENDPOINT if kind == "image" else VIDEO_ENDPOINT
        key = result_id(endpoint, params)

        entry = self.cache.get(key)
        if entry is None:
            data = self.client.get(endpoint, {**params, "per_page": API_PAGE_SIZE, "page": 1})
            entry = {
                "kind": kind,
                "endpoint": endpoint,
                "params": params,
                "hits": data.get("hits", []),
                "total": data.get("total", 0),
                "total_hits": data.get("totalHits", len(data.get("hits", []))),
                "pages_fetched": 1,
            }
            self.cache.set(key, entry)

        self._cursors[key] = 0
        return self._window(key, entry, full_tags)

    def paginate(self, key: str, full_tags: bool) -> Dict[str, Any]:
        entry = self.cache.get(key)
        if entry is None:
            raise ResultExpired(
                f"result_id '{key}' is unknown or expired (24h). Run the search again."
            )
        return self._window(key, entry, full_tags)

    def detail(self, key: str, hit_id: int) -> Dict[str, Any]:
        entry = self._require(key)
        hit = self._find_hit(entry, hit_id)
        return hit  # full raw record, straight from cache — no API call

    def get_hit(self, key: str, hit_id: int) -> Dict[str, Any]:
        """Raw hit lookup used by the download path."""
        return self._find_hit(self._require(key), hit_id)

    # ---- internals ----------------------------------------------------------

    def _require(self, key: str) -> Dict[str, Any]:
        entry = self.cache.get(key)
        if entry is None:
            raise ResultExpired(
                f"result_id '{key}' is unknown or expired (24h). Run the search again."
            )
        return entry

    @staticmethod
    def _find_hit(entry: Dict[str, Any], hit_id: int) -> Dict[str, Any]:
        for hit in entry["hits"]:
            if hit.get("id") == hit_id:
                return hit
        raise KeyError(
            f"hit id {hit_id} is not in result set (cached ids: "
            f"{[h.get('id') for h in entry['hits'][:20]]}…)"
        )

    def _window(self, key: str, entry: Dict[str, Any], full_tags: bool) -> Dict[str, Any]:
        offset = self._cursors.get(key, 0)

        # Fetch more server pages if the cursor would run past what's cached.
        while offset + SLICE_SIZE > len(entry["hits"]) and self._more_on_server(entry):
            self._fetch_next_page(key, entry)

        window = entry["hits"][offset : offset + SLICE_SIZE]
        self._cursors[key] = offset + len(window)

        slim = _SLIMMERS[entry["kind"]]
        hits = [slim(h, full_tags) for h in window]
        return {
            "result_id": key,
            "kind": entry["kind"],
            "offset": offset,
            "returned": len(hits),
            "total_hits": entry.get("total_hits"),
            "cached_hits": len(entry["hits"]),
            "more": self._cursors[key] < entry.get("total_hits", 0),
            "attribution_notice": (
                "Results from Pixabay (https://pixabay.com). Attribution required — "
                "keep each hit's 'attribution' when displaying or using an asset."
            ),
            "hits": hits,
        }

    @staticmethod
    def _more_on_server(entry: Dict[str, Any]) -> bool:
        return len(entry["hits"]) < entry.get("total_hits", 0)

    def _fetch_next_page(self, key: str, entry: Dict[str, Any]) -> None:
        next_page = entry["pages_fetched"] + 1
        data = self.client.get(
            entry["endpoint"],
            {**entry["params"], "per_page": API_PAGE_SIZE, "page": next_page},
        )
        new_hits = data.get("hits", [])
        if not new_hits:
            entry["total_hits"] = len(entry["hits"])  # server has no more
        else:
            entry["hits"].extend(new_hits)
            entry["pages_fetched"] = next_page
        self.cache.set(key, entry)  # created timestamp is preserved by DiskCache
