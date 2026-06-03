"""
Voyager API client base.

LinkedIn's internal Voyager API powers the web app. This module provides
an async HTTP client that injects auth headers and parses the
`application/vnd.linkedin.normalized+json+2.1` response format used by
most Voyager endpoints.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from auth import LinkedInAuth, load_auth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.linkedin.com/voyager/api"
DEFAULT_TIMEOUT = float(os.environ.get("LINKEDIN_REQUEST_TIMEOUT", "30"))


class VoyagerError(Exception):
    """Raised when the Voyager API returns an error response."""

    def __init__(self, status: int, message: str, url: str):
        self.status = status
        self.message = message
        self.url = url
        super().__init__(f"Voyager {status}: {message} ({url})")


class VoyagerClient:
    """
    Async HTTP client for the LinkedIn Voyager API.

    Usage:
        async with VoyagerClient() as client:
            data = await client.get("/identity/profiles/me")
    """

    def __init__(self, auth: LinkedInAuth | None = None, timeout: float = DEFAULT_TIMEOUT):
        self.auth = auth or load_auth()
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    async def __aenter__(self) -> VoyagerClient:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=self._timeout,
            headers=self.auth.headers(),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a Voyager endpoint. Raises VoyagerError on non-200."""
        if not self._client:
            raise RuntimeError("VoyagerClient must be used as an async context manager")

        response = await self._client.get(path, params=params)
        url = str(response.url)

        if response.status_code != 200:
            body_preview = response.text[:300] if response.text else ""
            raise VoyagerError(response.status_code, body_preview, url)

        try:
            return response.json()
        except Exception as e:
            raise VoyagerError(500, f"Invalid JSON: {e}", url) from e

    async def get_raw(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET a Voyager endpoint and return the raw response (no JSON parsing)."""
        if not self._client:
            raise RuntimeError("VoyagerClient must be used as an async context manager")
        return await self._client.get(path, params=params)


# ---------- Helpers used across tools ----------

def safe_int(value: Any) -> int:
    """Coerce arbitrary value to int, defaulting to 0."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def extract_hashtags(text: str) -> list[str]:
    """Extract #hashtags from post text."""
    import re

    return [m.group(1) for m in re.finditer(r"#([A-Za-z0-9_]+)", text)]


def extract_mentions(text: str) -> list[str]:
    """Extract @mentions from post text."""
    import re

    return [m.group(1) for m in re.finditer(r"@([A-Za-z0-9_-]+)", text)]
