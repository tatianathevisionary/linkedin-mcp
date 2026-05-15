"""Company typeahead search."""

from __future__ import annotations

from typing import Any

from voyager import VoyagerClient


async def search_companies(query: str, count: int = 10) -> list[dict[str, Any]]:
    """
    Typeahead-style company search.

    Returns: [{id, name, url, industry, headquarters}]
    """
    async with VoyagerClient() as client:
        data = await client.get(
            "/voyagerSearchDashClusters",
            params={
                "q": "all",
                "query": f"(keywords:{query})",
                "types": "COMPANIES",
                "count": str(min(max(count, 1), 50)),
                "decorationId": (
                    "com.linkedin.voyager.dash.deco.search.SearchClusterCollection-180"
                ),
            },
        )

    companies = []
    for cluster in (data.get("data") or {}).get("elements") or []:
        for item in cluster.get("items") or []:
            entity_result = item.get("item", {}).get("entityResult") or {}
            if not entity_result:
                continue
            urn = entity_result.get("trackingUrn") or entity_result.get("entityUrn") or ""
            company_id = urn.split(":")[-1] if ":" in urn else None
            companies.append({
                "id": company_id,
                "name": (entity_result.get("title") or {}).get("text"),
                "url": (entity_result.get("navigationUrl") or "").split("?")[0] or None,
                "industry": (entity_result.get("primarySubtitle") or {}).get("text"),
                "headquarters": (entity_result.get("secondarySubtitle") or {}).get("text"),
            })

    return companies
