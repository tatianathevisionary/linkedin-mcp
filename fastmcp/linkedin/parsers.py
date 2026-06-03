"""Shared parsers for LinkedIn Voyager API responses."""

from __future__ import annotations

from typing import Any

PROFILE_TYPE_PREFIX = "com.linkedin.voyager.dash.identity.profile."


def format_date(date_field: dict[str, Any] | None) -> str | None:
    """Format LinkedIn DateField (month/year) as 'YYYY-MM' or 'YYYY'."""
    if not date_field or not date_field.get("year"):
        return None
    year = date_field["year"]
    month = date_field.get("month")
    return f"{year}-{int(month):02d}" if month else str(year)


def group_by_type(included: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group LinkedIn 'included' array by $type field."""
    result: dict[str, list[dict[str, Any]]] = {}
    for item in included:
        type_key = item.get("$type", "unknown")
        result.setdefault(type_key, []).append(item)
    return result


def profile_type(suffix: str) -> str:
    """Build full profile entity type string."""
    return PROFILE_TYPE_PREFIX + suffix


def build_picture_url(pic: dict[str, Any] | None) -> str | None:
    """Build the highest-resolution profile picture URL from LinkedIn's artifacts array."""
    if not pic:
        return None
    root_url = pic.get("rootUrl")
    if not root_url:
        return None
    artifacts = pic.get("artifacts", [])
    if not artifacts:
        return root_url
    best = max(artifacts, key=lambda a: a.get("width", 0))
    segment = best.get("fileIdentifyingUrlPathSegment", "")
    return root_url + segment if segment else root_url


def parse_positions(entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Parse Position entities into normalized form."""
    emp_types = {
        e["entityUrn"]: e["name"]
        for e in entities.get(profile_type("EmploymentType"), [])
        if e.get("entityUrn") and e.get("name")
    }

    positions = []
    for p in entities.get(profile_type("Position"), []):
        dr = p.get("dateRange") or {}
        positions.append({
            "title": (p.get("title") or "").strip(),
            "companyName": (p.get("companyName") or "").strip(),
            "description": (p.get("description") or "").strip() or None,
            "location": (p.get("geoLocationName") or p.get("locationName") or "").strip() or None,
            "startDate": format_date(dr.get("start")),
            "endDate": format_date(dr.get("end")),
            "employmentType": emp_types.get(p.get("employmentTypeUrn")),
        })
    positions.sort(key=lambda x: x.get("startDate") or "", reverse=True)
    return positions


def parse_education(entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Parse Education entities."""
    education = []
    for e in entities.get(profile_type("Education"), []):
        dr = e.get("dateRange") or {}
        education.append({
            "schoolName": (e.get("schoolName") or "").strip(),
            "degreeName": (e.get("degreeName") or "").strip() or None,
            "fieldOfStudy": (e.get("fieldOfStudy") or "").strip() or None,
            "startDate": format_date(dr.get("start")),
            "endDate": format_date(dr.get("end")),
            "description": (e.get("description") or "").strip() or None,
        })
    education.sort(key=lambda x: x.get("startDate") or "", reverse=True)
    return education


def parse_skills(entities: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Parse Skill entities into a list of skill names."""
    return [
        (s.get("name") or "").strip()
        for s in entities.get(profile_type("Skill"), [])
        if s.get("name")
    ]


def parse_certifications(entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Parse Certification entities."""
    certs = []
    for c in entities.get(profile_type("Certification"), []):
        tp = c.get("timePeriod") or {}
        certs.append({
            "name": (c.get("name") or "").strip(),
            "authority": (c.get("authority") or "").strip() or None,
            "startDate": format_date(tp.get("start")),
            "endDate": format_date(tp.get("end")),
        })
    return certs


def parse_projects(entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Parse Project entities."""
    projects = []
    for p in entities.get(profile_type("Project"), []):
        dr = p.get("dateRange") or {}
        projects.append({
            "title": (p.get("title") or "").strip(),
            "description": (p.get("description") or "").strip() or None,
            "url": p.get("url"),
            "startDate": format_date(dr.get("start")),
            "endDate": format_date(dr.get("end")),
        })
    return projects


def parse_languages(entities: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Parse Language entities."""
    return [
        (lang.get("name") or "").strip()
        for lang in entities.get(profile_type("Language"), [])
        if lang.get("name")
    ]


def extract_public_id(input_str: str) -> str:
    """Extract LinkedIn vanity name from a URL or bare username."""
    import re
    trimmed = input_str.strip()
    match = re.search(r"linkedin\.com/in/([^/?#]+)", trimmed, re.IGNORECASE)
    if match:
        return match.group(1)
    return trimmed.strip("/")
