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

import logging
from typing import Any, Literal

from voyager import VoyagerClient, VoyagerError

from .parsers import build_picture_url

logger = logging.getLogger(__name__)

NETWORK_MAP = {"1st": "F", "2nd": "S", "3rd": "O"}


def _is_auth_error(exc: Exception) -> bool:
    """True if the exception is a LinkedIn auth failure (401/403)."""
    return isinstance(exc, VoyagerError) and exc.status in (401, 403)


async def search_people(
    keywords: str,
    network: list[Literal["1st", "2nd", "3rd"]] | None = None,
    location: str | None = None,
    count: int = 25,
    start: int = 0,
) -> dict[str, Any]:
    """
    Search LinkedIn people via connections (1st-degree) + global typeahead.

    Client-side filters (applied to whatever the Voyager responses return):
      - `network`: connection degree. Connections search only surfaces
        1st-degree, so 2nd/3rd only match typeahead results that expose a
        degree. Results with an unknown degree are kept when 2nd/3rd is
        requested (best-effort — degree is often absent from typeahead).
      - `location`: case-insensitive substring match against each result's
        `location` field.

    Note: `company` and `school` filters are intentionally NOT supported —
    the mini-profile responses don't include those fields, so filtering on
    them would silently drop everything. Use `fetch_linkedin_person` for
    per-profile company/school detail.

    Returns: { total, people: [...], paging: { start, count } }
    """
    async with VoyagerClient() as client:
        results: list[dict[str, Any]] = []
        total = 0

        # Strategy 1: search own connections (1st-degree).
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

            # Resolve each connection to a mini-profile.
            for member_id in member_ids[: min(count, 25)]:
                try:
                    profile = await _resolve_profile(client, member_id)
                    if profile:
                        results.append(profile)
                except VoyagerError as e:
                    if _is_auth_error(e):
                        logger.warning(
                            "Auth failure (%s) resolving connection %s — cookie likely expired",
                            e.status, member_id,
                        )
                        raise
                    logger.warning("Failed to resolve connection %s: %s", member_id, e)
                    continue
                except Exception as e:  # noqa: BLE001
                    logger.warning("Failed to resolve connection %s: %s", member_id, e)
                    continue
        except VoyagerError as e:
            if _is_auth_error(e):
                # Surface expired/invalid cookie clearly instead of returning empty.
                logger.error("People search auth failure (%s) — LinkedIn cookie is invalid or expired", e.status)
                raise
            logger.warning("Connections search failed (%s) — falling through to typeahead", e)
        except Exception as e:  # noqa: BLE001
            logger.warning("Connections search failed: %s — falling through to typeahead", e)

        # Strategy 2: global typeahead for cross-network results.
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

                    # Skip if already in results.
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
            except VoyagerError as e:
                if _is_auth_error(e):
                    logger.error("Typeahead auth failure (%s) — LinkedIn cookie is invalid or expired", e.status)
                    raise
                logger.warning("Typeahead search failed (%s)", e)
            except Exception as e:  # noqa: BLE001
                logger.warning("Typeahead search failed: %s", e)

        # ---- Client-side filtering on fields the results actually expose ----
        filtered = _apply_filters(results, network=network, location=location)

        return {
            "total": max(total, len(filtered)),
            "people": filtered[:count],
            "paging": {"start": start, "count": len(filtered[:count])},
        }


def _apply_filters(
    people: list[dict[str, Any]],
    network: list[Literal["1st", "2nd", "3rd"]] | None,
    location: str | None,
) -> list[dict[str, Any]]:
    """Filter merged people results by network degree and/or location substring."""
    out = people

    if network:
        wanted = set(network)
        # 1st-degree is reliably known (connections). For 2nd/3rd the degree is
        # frequently absent from typeahead, so keep unknown-degree results when
        # a non-1st degree is requested rather than dropping everything.
        allow_unknown = bool(wanted - {"1st"})
        out = [
            p for p in out
            if (p.get("connectionDegree") in wanted)
            or (allow_unknown and p.get("connectionDegree") is None)
        ]

    if location:
        loc_lower = location.lower()
        out = [
            p for p in out
            if (p.get("location") or "").lower().find(loc_lower) >= 0
        ]

    return out


async def _resolve_profile(client: VoyagerClient, member_id: str) -> dict[str, Any] | None:
    """
    Resolve a member URN to a mini-profile via dash/profiles.

    Auth errors (401/403) propagate so the caller can surface an expired
    cookie. Other errors return None (this single profile is skippable).
    """
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
    except VoyagerError as e:
        if _is_auth_error(e):
            raise
        logger.warning("Profile resolution failed for %s: %s", member_id, e)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("Profile resolution failed for %s: %s", member_id, e)
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
