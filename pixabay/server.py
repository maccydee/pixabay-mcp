"""FastMCP wrapper exposing the Pixabay tools over stdio.

Run directly (`python -m pixabay.server`) or via run_server.py from an MCP client.
"""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from .cache import DiskCache
from .client import PixabayClient, PixabayError
from .config import CACHE_TTL_SECONDS, Config
from .library import Library
from .projections import IMAGE_SIZE_FIELDS, attribution_notice
from .search import ResultExpired, SearchService

CFG = Config.from_env()
CLIENT = PixabayClient(CFG.api_key)
CACHE = DiskCache(CFG.cache_dir, CACHE_TTL_SECONDS)
SEARCH = SearchService(CLIENT, CACHE)
LIBRARY = Library(CFG.library_dir, CFG.manifest_path)

mcp = FastMCP("pixabay")


def _guard(fn):
    """Turn expected failures into friendly dicts instead of raw tracebacks."""
    try:
        return fn()
    except ResultExpired as exc:
        return {"error": "result_expired", "message": str(exc)}
    except (PixabayError, KeyError, ValueError) as exc:
        return {"error": type(exc).__name__, "message": str(exc)}


@mcp.tool()
def search_images(
    query: str,
    image_type: str = "all",
    orientation: str = "all",
    category: str = "",
    colors: str = "",
    editors_choice: bool = False,
    order: str = "popular",
    min_width: int = 0,
    min_height: int = 0,
    safesearch: bool = True,
    lang: str = "en",
    full_tags: bool = False,
) -> Dict[str, Any]:
    """Search Pixabay images. Returns ~12 slim hits plus a result_id for paging.

    image_type: all|photo|illustration|vector. orientation: all|horizontal|vertical.
    order: popular|latest. category e.g. nature, backgrounds, people (see Pixabay docs).
    colors: comma list e.g. red,blue,grayscale. Use paginate(result_id) for more.
    """
    params = {
        "q": query,
        "image_type": image_type,
        "orientation": orientation,
        "category": category,
        "colors": colors,
        "editors_choice": editors_choice,
        "order": order,
        "min_width": min_width,
        "min_height": min_height,
        "safesearch": safesearch,
        "lang": lang,
    }
    return _guard(lambda: SEARCH.search("image", params, full_tags))


@mcp.tool()
def search_videos(
    query: str,
    video_type: str = "all",
    category: str = "",
    order: str = "popular",
    min_width: int = 0,
    min_height: int = 0,
    safesearch: bool = True,
    lang: str = "en",
    full_tags: bool = False,
) -> Dict[str, Any]:
    """Search Pixabay videos. Each hit lists its available renditions/sizes.

    video_type: all|film|animation. order: popular|latest. Use paginate() for more.
    """
    params = {
        "q": query,
        "video_type": video_type,
        "category": category,
        "order": order,
        "min_width": min_width,
        "min_height": min_height,
        "safesearch": safesearch,
        "lang": lang,
    }
    return _guard(lambda: SEARCH.search("video", params, full_tags))


@mcp.tool()
def paginate(result_id: str, full_tags: bool = False) -> Dict[str, Any]:
    """Return the next slim slice for a prior search's result_id.

    Free from the 24h cache when possible; only calls the API if the cursor runs
    past the cached hits and more exist server-side.
    """
    return _guard(lambda: SEARCH.paginate(result_id, full_tags))


@mcp.tool()
def get_detail(result_id: str, hit_id: int) -> Dict[str, Any]:
    """Full raw record for one hit, straight from cache (no API call)."""
    return _guard(lambda: SEARCH.detail(result_id, hit_id))


@mcp.tool()
def download_asset(result_id: str, hit_id: int, size: str = "web") -> Dict[str, Any]:
    """Download one asset to the server library and return its path + attribution.

    Image sizes: preview, web, large, fullhd, original, vector (last three need a
    full-API-access account). Video sizes: large, medium, small, tiny.
    """
    def _run() -> Dict[str, Any]:
        hit = SEARCH.get_hit(result_id, hit_id)
        kind = "image" if "imageWidth" in hit or "webformatURL" in hit else "video"

        if kind == "image":
            field = IMAGE_SIZE_FIELDS.get(size)
            if field is None:
                return {
                    "error": "bad_size",
                    "message": f"Unknown image size '{size}'. Choose from {list(IMAGE_SIZE_FIELDS)}.",
                }
            url = hit.get(field)
        else:
            rendition = (hit.get("videos", {}) or {}).get(size, {})
            url = rendition.get("url")

        if not url:
            available = (
                [s for s, f in IMAGE_SIZE_FIELDS.items() if hit.get(f)]
                if kind == "image"
                else [s for s, v in (hit.get("videos", {}) or {}).items() if v.get("url")]
            )
            return {
                "error": "size_unavailable",
                "message": f"Size '{size}' not available for hit {hit_id}. Available: {available}.",
            }

        record = LIBRARY.download(hit, size, url, kind)
        return {
            "path": record["path"],
            "bytes": record["bytes"],
            "size": size,
            "kind": kind,
            "deduped": record.get("deduped", False),
            "attribution": record["attribution"],
            "attribution_notice": record["attribution_notice"],
        }

    return _guard(_run)


@mcp.tool()
def library_list() -> Dict[str, Any]:
    """List assets already downloaded to the server library."""
    return _guard(lambda: {"count": LIBRARY.count(), "entries": LIBRARY.list()})


@mcp.tool()
def library_remove(entry_id: str) -> Dict[str, Any]:
    """Remove one downloaded asset (by entry_id, e.g. '12345-web') from the library."""
    return _guard(lambda: LIBRARY.remove(entry_id))


@mcp.tool()
def status() -> Dict[str, Any]:
    """Report key mode, cache/library location, and current rate-limit headers."""
    return {
        "using_demo_key": CFG.using_demo_key,
        "api_key": CFG.masked_key(),
        "data_dir": str(CFG.data_dir),
        "cache_dir": str(CFG.cache_dir),
        "library_dir": str(CFG.library_dir),
        "cache_entries": len(CACHE.keys()),
        "library_entries": LIBRARY.count(),
        "rate_limit": CLIENT.rate.as_dict(),
        "note": (
            "Using the shared demo key — add your own PIXABAY_API_KEY for real use."
            if CFG.using_demo_key
            else "Using your PIXABAY_API_KEY."
        ),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
