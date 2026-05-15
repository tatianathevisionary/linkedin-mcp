"""
Company typeahead search.

Uses LinkedIn's `/jobs-guest/api/typeaheadHits` endpoint — the lightweight
typeahead used by the LinkedIn web app's company-picker dropdowns. No CSRF
required, no X-Restli, just basic Cookie + User-Agent headers.

This endpoint is what the TS edition uses and it works reliably. The heavier
`voyagerSearchDashClusters` endpoint returns 403/500 on most calls.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from auth import LinkedInAuth, load_auth

TYPEAHEAD_URL = "https://www.linkedin.com/jobs-guest/api/typeaheadHits"
DEFAULT_TIMEOUT = float(os.environ.get("LINKEDIN_REQUEST_TIMEOUT", "30"))


async def search_companies(query: str, count: int = 10) -> list[dict[str, Any]]:
    """
    Typeahead-style company search via the guest jobs API.

    Returns: [{id, name, url}]
    """
    auth: LinkedInAuth = load_auth()

    headers = {
        "Cookie": auth.cookie_header,
        "User-Agent": auth.user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    params = {
        "typeaheadType": "COMPANY",
        "query": query,
    }

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(TYPEAHEAD_URL, params=params, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(
            f"LinkedIn typeaheadHits {response.status_code}: "
            f"{response.text[:200] if response.text else ''}"
        )

    data = response.json()
    elements = data if isinstance(data, list) else data.get("elements", [])

    return [
        {
            "id": str(el.get("id", "")),
            "name": el.get("displayName") or "Unknown",
            "url": el.get("navigationUrl"),
            "trackingId": el.get("trackingId"),
        }
        for el in elements[: min(max(count, 1), 50)]
    ]
