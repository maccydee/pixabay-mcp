"""Slim projections of raw Pixabay hits + attribution helpers.

Raw hits carry ~25 fields; the model only needs a handful to decide what to
fetch or download. Everything else stays in the cache and is available via
get_detail without spending tokens.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .config import DEFAULT_TAG_LIMIT

# size name -> field on an image hit
IMAGE_SIZE_FIELDS = {
    "preview": "previewURL",
    "web": "webformatURL",
    "large": "largeImageURL",
    "fullhd": "fullHDURL",     # full-API-access accounts only
    "original": "imageURL",    # full-API-access accounts only
    "vector": "vectorURL",     # full-API-access accounts only
}
VIDEO_SIZES = ("large", "medium", "small", "tiny")


def _tags(hit: Dict[str, Any], full_tags: bool) -> List[str]:
    tags = [t.strip() for t in str(hit.get("tags", "")).split(",") if t.strip()]
    return tags if full_tags else tags[:DEFAULT_TAG_LIMIT]


def attribution(hit: Dict[str, Any]) -> str:
    """Short credit line to display next to any shown/used asset."""
    user = hit.get("user", "unknown")
    return f"{user} on Pixabay"


def attribution_notice(hit: Dict[str, Any]) -> str:
    """Full credit line with a link back to Pixabay (satisfies their terms)."""
    user = hit.get("user", "unknown")
    page = hit.get("pageURL", "https://pixabay.com")
    return f"Media by {user} from Pixabay — {page}"


def slim_image(hit: Dict[str, Any], full_tags: bool = False) -> Dict[str, Any]:
    return {
        "id": hit.get("id"),
        "tags": _tags(hit, full_tags),
        "width": hit.get("imageWidth"),
        "height": hit.get("imageHeight"),
        "preview_url": hit.get("previewURL"),
        "web_url": hit.get("webformatURL"),
        "by": hit.get("user"),
        "page_url": hit.get("pageURL"),
        "available_sizes": [s for s, f in IMAGE_SIZE_FIELDS.items() if hit.get(f)],
        "attribution": attribution(hit),
    }


def slim_video(hit: Dict[str, Any], full_tags: bool = False) -> Dict[str, Any]:
    videos = hit.get("videos", {}) or {}
    renditions = {}
    thumbnail = None
    for size in VIDEO_SIZES:
        v = videos.get(size)
        if v and v.get("url"):
            renditions[size] = {
                "width": v.get("width"),
                "height": v.get("height"),
                "size_bytes": v.get("size"),
            }
            thumbnail = thumbnail or v.get("thumbnail")
    return {
        "id": hit.get("id"),
        "tags": _tags(hit, full_tags),
        "duration_seconds": hit.get("duration"),
        "thumbnail_url": thumbnail,
        "renditions": renditions,
        "by": hit.get("user"),
        "page_url": hit.get("pageURL"),
        "attribution": attribution(hit),
    }
