"""People search via connections + typeahead."""

from __future__ import annotations

from typing import Any, Literal, Optional

from voyager import VoyagerClient

NETWORK_MAP = {"1st": "F", "2nd": "S", "3rd": "O"}


async def search_people(
    keywords: str,
    network: Optional[list[Literal["1st", "2nd", "3rd"]]] = None,
    company: Optional[str] = None,
    school: Optional[str] = None,
    location: Optional[str] = None,
    count: int = 25,
    start: int = 0,
) -> dict[str, Any]:
    """
    Search LinkedIn people via Voyager search clusters.

    Returns: { total, people: [{publicIdentifier, fullName, headline, location, profileUrl, connectionDegree}] }
    """
    filters = []
    if network:
        codes = [NETWORK_MAP[n] for n in network if n in NETWORK_MAP]
        if codes:
            filters.append(f"network->{'|'.join(codes)}")
    if company:
        filters.append(f"currentCompany->{company}")
    if school:
        filters.append(f"school->{school}")
    if location:
        filters.append(f"geoUrn->{location}")

    query_parts = [f"keywords:{keywords}"]
    if filters:
        query_parts.append(f"selectedFilters:(List({','.join(filters)}))")
    query = "(" + ",".join(query_parts) + ")"

    async with VoyagerClient() as client:
        data = await client.get(
            "/voyagerSearchDashClusters",
            params={
                "q": "all",
                "query": query,
                "types": "PEOPLE",
                "count": str(min(max(count, 1), 50)),
                "start": str(start),
                "decorationId": (
                    "com.linkedin.voyager.dash.deco.search.SearchClusterCollection-180"
                ),
            },
        )

    people = []
    for cluster in (data.get("data") or {}).get("elements") or []:
        for item in cluster.get("items") or []:
            er = item.get("item", {}).get("entityResult") or {}
            if not er:
                continue
            nav_url = er.get("navigationUrl") or ""
            # Extract vanity from nav URL
            vanity = None
            if "/in/" in nav_url:
                vanity = nav_url.split("/in/")[1].split("/")[0].split("?")[0]

            people.append({
                "publicIdentifier": vanity,
                "fullName": (er.get("title") or {}).get("text"),
                "headline": (er.get("primarySubtitle") or {}).get("text"),
                "location": (er.get("secondarySubtitle") or {}).get("text"),
                "profileUrl": f"https://www.linkedin.com/in/{vanity}" if vanity else None,
                "connectionDegree": (er.get("badgeText") or {}).get("accessibilityText"),
            })

    paging = (data.get("data") or {}).get("paging") or {}
    return {
        "total": paging.get("total", len(people)),
        "people": people,
        "paging": {"start": paging.get("start", start), "count": paging.get("count", count)},
    }
