"""Environment-driven configuration: API key and on-disk paths.

All state lives under PIXABAY_DATA_DIR (default ~/.pixabay-plugin):
    <data_dir>/cache/       24h response cache (one JSON file per result_id)
    <data_dir>/library/     downloaded assets + manifest.json
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Pixabay's publicly documented demo key. Heavily rate-limited and may be
# disabled at any time — only a convenience for a first smoke test.
DEMO_API_KEY = "9656065-a4094594c34f9ac14c7fc4c39"

CACHE_TTL_SECONDS = 24 * 60 * 60  # Pixabay terms require 24h caching.
API_PAGE_SIZE = 50                # hits fetched per real API request
SLICE_SIZE = 12                   # slim hits handed back to the model per call
DEFAULT_TAG_LIMIT = 8             # tags kept per hit unless full_tags=True


@dataclass(frozen=True)
class Config:
    api_key: str
    using_demo_key: bool
    data_dir: Path
    cache_dir: Path
    library_dir: Path
    manifest_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        key = os.environ.get("PIXABAY_API_KEY", "").strip()
        using_demo = not key
        if using_demo:
            key = DEMO_API_KEY

        data_dir = Path(
            os.environ.get("PIXABAY_DATA_DIR", "~/.pixabay-plugin")
        ).expanduser()
        cache_dir = data_dir / "cache"
        library_dir = data_dir / "library"

        for d in (data_dir, cache_dir, library_dir):
            d.mkdir(parents=True, exist_ok=True)

        return cls(
            api_key=key,
            using_demo_key=using_demo,
            data_dir=data_dir,
            cache_dir=cache_dir,
            library_dir=library_dir,
            manifest_path=library_dir / "manifest.json",
        )

    def masked_key(self) -> str:
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}…{self.api_key[-4:]}"
