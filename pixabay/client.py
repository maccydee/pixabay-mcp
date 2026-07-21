"""Thin stdlib HTTP client for the Pixabay REST API with 429 backoff.

No third-party HTTP dependency — just urllib. Reads the rate-limit headers
Pixabay returns (X-RateLimit-Limit / -Remaining / -Reset) and honours 429s.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

IMAGE_ENDPOINT = "https://pixabay.com/api/"
VIDEO_ENDPOINT = "https://pixabay.com/api/videos/"

_USER_AGENT = "pixabay-mcp/1.0 (+https://modelcontextprotocol.io)"


class PixabayError(RuntimeError):
    """Any API-, network-, or rate-limit-level failure."""


class RateLimitState:
    def __init__(self) -> None:
        self.limit: int | None = None
        self.remaining: int | None = None
        self.reset: int | None = None  # seconds until the window resets

    def update(self, headers) -> None:
        def _int(name):
            v = headers.get(name)
            try:
                return int(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        self.limit = _int("X-RateLimit-Limit") or self.limit
        self.remaining = _int("X-RateLimit-Remaining")
        self.reset = _int("X-RateLimit-Reset")

    def as_dict(self) -> Dict[str, Any]:
        return {"limit": self.limit, "remaining": self.remaining, "reset_seconds": self.reset}


class PixabayClient:
    def __init__(self, api_key: str, timeout: float = 30.0, max_retries: int = 3) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate = RateLimitState()

    def get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = endpoint + "?" + urllib.parse.urlencode(self._normalize(params))
        last_err: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    self.rate.update(resp.headers)
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                self.rate.update(exc.headers)
                if exc.code == 429 and attempt < self.max_retries:
                    time.sleep(self._retry_after(exc.headers, attempt))
                    last_err = PixabayError("Rate limited (429) by Pixabay.")
                    continue
                body = exc.read().decode("utf-8", "replace")[:300] if exc.fp else ""
                raise PixabayError(f"Pixabay API error {exc.code}: {body or exc.reason}") from exc
            except urllib.error.URLError as exc:
                last_err = PixabayError(f"Network error contacting Pixabay: {exc.reason}")
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise last_err from exc

        raise last_err or PixabayError("Request failed for an unknown reason.")

    def _normalize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize params, dropping Pixabay defaults and adding the key.

        Bools become "true"/"false"; None/""/0/False are dropped (they all map
        to Pixabay defaults) except page/per_page which are always sent.
        """
        out: Dict[str, Any] = {"key": self.api_key}
        for key, value in params.items():
            if key in ("page", "per_page"):
                out[key] = value
                continue
            if value is None or value == "" or value is False or value == 0:
                continue
            if value is True:
                out[key] = "true"
            else:
                out[key] = value
        return out

    @staticmethod
    def _retry_after(headers, attempt: int) -> float:
        retry_after = headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
        reset = headers.get("X-RateLimit-Reset")
        if reset:
            try:
                return min(float(reset), 60.0)
            except ValueError:
                pass
        return float(2 ** attempt)  # exponential fallback: 1, 2, 4, 8 …
