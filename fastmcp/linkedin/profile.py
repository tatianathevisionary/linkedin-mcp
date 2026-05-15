"""Profile tools · fetch the logged-in user's profile or any user's profile by vanity."""

from __future__ import annotations

import re
from typing import Any, Optional

from voyager import VoyagerClient

from .parsers import (
    build_picture_url,
    extract_public_id,
    group_by_type,
    parse_certifications,
    parse_education,
    parse_languages,
    parse_positions,
    parse_projects,
    parse_skills,
    profile_type,
)


async def fetch_profile() -> Optional[dict[str, Any]]:
    """
    Fetch the FULL profile of the currently logged-in LinkedIn user.

    Returns a dict with: id, firstName, lastName, headline, summary, profilePicture,
    profileUrl, location, emails, positions, education, skills, certifications, projects.

    Returns None if the profile can't be resolved.
    """
    async with VoyagerClient() as client:
        # Step 1: Get our profile ID via job seeker preferences
        prefs = await client.get(
            "/voyagerJobsDashJobSeekerPreferences",
            params={"decorationId": "com.linkedin.voyager.dash.deco.jobs.FullJobSeekerPreference-8"},
        )
        entity_urn = (prefs.get("data") or {}).get("entityUrn") or ""
        match = re.search(r"ACo[A-Za-z0-9_-]+", entity_urn)
        if not match:
            return None
        profile_id = match.group(0)

        # Step 2: Basic profile (emails, profile picture, publicIdentifier)
        basic = await client.get(
            f"/identity/normalizedProfiles/{profile_id}",
            params={
                "decorationId": (
                    "com.linkedin.voyager.deco.identity.normalizedprofile.shared."
                    "WebApplicantProfile-13"
                )
            },
        )
        public_id = (basic.get("data") or {}).get("publicIdentifier")
        if not public_id:
            return None

        # Step 3: Full profile with entities
        full = await client.get(
            "/identity/dash/profiles",
            params={
                "q": "memberIdentity",
                "memberIdentity": public_id,
                "decorationId": (
                    "com.linkedin.voyager.dash.deco.identity.profile."
                    "FullProfileWithEntities-93"
                ),
            },
        )

    entities = group_by_type(full.get("included") or [])

    # Find own profile
    profile_data = next(
        (
            p
            for p in entities.get(profile_type("Profile"), [])
            if profile_id in (p.get("entityUrn") or "")
        ),
        None,
    )

    # Emails from basic profile
    emails = [
        item["email"]
        for item in (basic.get("included") or [])
        if isinstance(item.get("email"), str)
    ]

    d = basic.get("data") or {}
    loc = d.get("location") or {}

    return {
        "id": profile_id,
        "firstName": (d.get("firstName") or "").strip(),
        "lastName": (d.get("lastName") or "").strip(),
        "headline": (d.get("headline") or "").strip() or None,
        "summary": (profile_data or {}).get("summary"),
        "profilePicture": build_picture_url(d.get("profilePicture")),
        "profileUrl": f"https://www.linkedin.com/in/{public_id}" if public_id else None,
        "location": loc.get("locationDisplayName") or loc.get("defaultLocalizedName"),
        "emails": emails or None,
        "positions": parse_positions(entities),
        "education": parse_education(entities),
        "skills": parse_skills(entities),
        "certifications": parse_certifications(entities),
        "projects": parse_projects(entities),
        "languages": parse_languages(entities),
    }


async def fetch_person(profile_input: str) -> Optional[dict[str, Any]]:
    """
    Fetch any LinkedIn person's profile by vanity name or LinkedIn URL.

    Accepts:
    - "johndoe"
    - "https://linkedin.com/in/johndoe"
    - "https://www.linkedin.com/in/johndoe/"
    """
    public_id = extract_public_id(profile_input)
    if not public_id:
        return None

    async with VoyagerClient() as client:
        full = await client.get(
            "/identity/dash/profiles",
            params={
                "q": "memberIdentity",
                "memberIdentity": public_id,
                "decorationId": (
                    "com.linkedin.voyager.dash.deco.identity.profile."
                    "FullProfileWithEntities-93"
                ),
            },
        )

    included = full.get("included") or []
    if not included:
        return None

    entities = group_by_type(included)
    profile_entities = entities.get(profile_type("Profile"), [])

    profile_data = next(
        (p for p in profile_entities if p.get("publicIdentifier") == public_id),
        profile_entities[0] if profile_entities else None,
    )
    if not profile_data:
        return None

    # Geo location
    geo = profile_data.get("geoLocation") or profile_data.get("location") or {}
    geo_inner = geo.get("geo") or {}
    location_name = (
        geo_inner.get("defaultLocalizedName")
        or profile_data.get("geoLocationName")
        or profile_data.get("locationName")
    )

    # Network info (connection degree, count)
    network_info = next(
        (i for i in included if i.get("$type") == profile_type("NetworkInfo")),
        None,
    )
    connection_degree = ((network_info or {}).get("distance") or {}).get("value")
    connections_count = (network_info or {}).get("connectionsCount")

    return {
        "publicIdentifier": public_id,
        "firstName": (profile_data.get("firstName") or "").strip(),
        "lastName": (profile_data.get("lastName") or "").strip(),
        "headline": (profile_data.get("headline") or "").strip() or None,
        "summary": (profile_data.get("summary") or "").strip() or None,
        "profilePicture": build_picture_url(profile_data.get("profilePicture")),
        "profileUrl": f"https://www.linkedin.com/in/{public_id}",
        "location": location_name,
        "industry": (profile_data.get("industryName") or "").strip() or None,
        "connectionDegree": connection_degree,
        "connectionsCount": connections_count,
        "positions": parse_positions(entities),
        "education": parse_education(entities),
        "skills": parse_skills(entities),
        "certifications": parse_certifications(entities),
        "projects": parse_projects(entities),
        "languages": parse_languages(entities),
    }
