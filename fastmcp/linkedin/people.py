"""
People search.

The general `voyagerSearchDashClusters` endpoint returns 500/403 across all
decoration IDs (as of early 2026 per the TS edition's notes). This module
uses two reliable fallback strategies instead:

1. **Connections search** — `/relationships/dash/connections` searches your
   own connection graph. Best for finding 1st-degree people.

2. **Global typeahead** — `/voyagerSearchDashTypeahead` returns a small set
   of cross-network people suggestions. Best for finding 2nd/3rd-degree.

Together these cover most real "find a person" use cases.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from voyager import VoyagerClient

from .parsers import build_picture_url

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
    Search LinkedIn people via connections (1st-degree) + global typeahead.

    Returns: { total, people: [...], paging: { start, count } }
    """
    # Connections search has its own Referer
    async with VoyagerClient() as client:
        results: list[dict[str, Any]] = []
        total = 0

        # Strategy 1: search own connections
        try:
            conn_data = await client.get(
                "/relationships/dash/connections",
                params={
                    "q": "search",
                    "keywords": keywords,
                    "count": str(min(max(count, 1), 50)),
                    "start": str(start),
                    "sortType": "RECENTLY_ADDED",
                },
            )
            included = conn_data.get("included") or []
            paging = (conn_data.get("data") or {}).get("paging") or {}
            total = paging.get("total", 0)

            member_ids: list[str] = []
            for item in included:
                if item.get("$type") == "com.linkedin.voyager.dash.relationships.Connection":
                    urn = item.get("connectedMember") or ""
                    if "fsd_profile:" in urn:
                        member_ids.append(urn.split("fsd_profile:", 1)[1])

            # Resolve each connection to a mini-profile
            for member_id in member_ids[: min(count, 25)]:
                try:
                    profile = await _resolve_profile(client, member_id)
                    if profile:
                        results.append(profile)
                except Exception:
                    continue
        except Exception:
            # Connections search may fail — fall through to typeahead
            pass

        # Strategy 2: global typeahead for cross-network results
        if len(results) < count:
            try:
                ta_data = await client.get(
                    "/voyagerSearchDashTypeahead",
                    params={"q": "globalTypeahead", "query": keywords},
                )
                elements = (ta_data.get("data") or {}).get("elements") or []
                for el in elements:
                    if el.get("suggestionType") != "ENTITY_TYPEAHEAD":
                        continue
                    lockup = el.get("entityLockupView")
                    if not lockup:
                        continue
                    nav_url = lockup.get("navigationUrl") or ""
                    if "/in/" not in nav_url:
                        continue
                    public_id_part = nav_url.split("/in/", 1)[1].split("?")[0].split("/")[0]
                    title = (lockup.get("title") or {}).get("text") or ""
                    subtitle = (lockup.get("subtitle") or {}).get("text") or ""

                    # Skip if already in results
                    if any(p.get("publicIdentifier") == public_id_part for p in results):
                        continue

                    name_parts = title.split(" ", 1)
                    results.append({
                        "publicIdentifier": public_id_part,
                        "fullName": title,
                        "firstName": name_parts[0] if name_parts else "",
                        "lastName": name_parts[1] if len(name_parts) > 1 else "",
                        "headline": subtitle or None,
                        "location": None,
                        "profileUrl": f"https://www.linkedin.com/in/{public_id_part}",
                        "connectionDegree": None,
                    })
                    if len(results) >= count:
                        break
            except Exception:
                pass

        return {
            "total": max(total, len(results)),
            "people": results[:count],
            "paging": {"start": start, "count": len(results[:count])},
        }


async def _resolve_profile(client: VoyagerClient, member_id: str) -> Optional[dict[str, Any]]:
    """Resolve a member URN to a mini-profile via dash/profiles."""
    try:
        data = await client.get(
            "/identity/dash/profiles",
            params={
                "q": "memberIdentity",
                "memberIdentity": member_id,
                "decorationId": (
                    "com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-185"
                ),
            },
        )
    except Exception:
        return None

    included = data.get("included") or []
    profile = next(
        (i for i in included if i.get("$type") == "com.linkedin.voyager.dash.identity.profile.Profile"),
        None,
    )
    if not profile:
        return None

    public_id = profile.get("publicIdentifier") or member_id
    return {
        "publicIdentifier": public_id,
        "fullName": f"{(profile.get('firstName') or '').strip()} {(profile.get('lastName') or '').strip()}".strip(),
        "firstName": (profile.get("firstName") or "").strip(),
        "lastName": (profile.get("lastName") or "").strip(),
        "headline": (profile.get("headline") or "").strip() or None,
        "location": (profile.get("geoLocationName") or profile.get("locationName") or "").strip() or None,
        "profileUrl": f"https://www.linkedin.com/in/{public_id}",
        "profilePicture": build_picture_url(profile.get("profilePicture")),
        "connectionDegree": "1st",
    }
