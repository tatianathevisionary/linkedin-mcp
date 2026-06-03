"""Job search + single job fetch."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal
from urllib.parse import quote

from voyager import VoyagerClient

logger = logging.getLogger(__name__)

DECORATION = "com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-218"
JOB_POSTING_CARD_TYPE = "com.linkedin.voyager.dash.jobs.JobPostingCard"

# Map friendly Literal values to the codes LinkedIn's :List(...) filters expect.
WORKPLACE_MAP = {"onsite": 1, "remote": 2, "hybrid": 3}
JOBTYPE_MAP = {
    "fulltime": "F",
    "parttime": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
}
TIMEPOSTED_MAP = {"past_24h": "r86400", "past_week": "r604800", "past_month": "r2592000"}
EXPERIENCE_MAP = {
    "intern": 1,
    "entry": 2,
    "associate": 3,
    "mid_senior": 4,
    "director": 5,
    "executive": 6,
}


async def _resolve_geo_id(client: VoyagerClient, location: str) -> str | None:
    """
    Resolve a free-text location to a LinkedIn geoId.

    Mirrors the verified TS edition (`src/clients/linkedin/search-jobs.ts`):
    LinkedIn embeds an `fsd_geo:<id>` token in the jobs search HTML page for
    the resolved location. We fetch that page and scrape the first match.

    Best-effort: returns None if the page can't be fetched or parsed (e.g.
    expired cookie). The caller falls back to a location-free query.
    """
    try:
        url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords=test&location={quote(location)}"
        )
        resp = await client.get_raw(url)
        if resp.status_code != 200:
            logger.warning("geoId resolution returned HTTP %s for %r", resp.status_code, location)
            return None
        match = re.search(r"fsd_geo:(\d+)", resp.text)
        return match.group(1) if match else None
    except Exception as e:  # noqa: BLE001 - best-effort, never fatal
        logger.warning("geoId resolution failed for %r: %s", location, e)
        return None


def _build_query(keywords: str, geo_id: str | None, filters: list[str]) -> str:
    """
    Build the Voyager `query` param using `:List(...)` filter encoding.

    Matches the verified TS edition exactly:
      (origin:JOB_SEARCH_PAGE_QUERY_EXPANSION,keywords:<kw>
       [,locationUnion:(geoId:<id>)],selectedFilters:(<f1>,<f2>,...))
    """
    location_part = f",locationUnion:(geoId:{geo_id})" if geo_id else ""
    filter_str = ",".join(filters)
    return (
        f"(origin:JOB_SEARCH_PAGE_QUERY_EXPANSION,keywords:{quote(keywords)}"
        f"{location_part},selectedFilters:({filter_str}))"
    )


def _parse_jobs(data: dict[str, Any], start: int, count: int) -> dict[str, Any]:
    """
    Parse the Voyager jobs response into a normalized job list.

    Robust to BOTH known response shapes:

    1. **included[] shape** (verified-working, matches the TS edition):
       results live in `data.included[]`, filtered to entries whose `$type`
       contains ``JobPostingCard``. This is the primary path.

    2. **data.elements[].jobCardUnion shape** (legacy half-port): some
       decoration IDs nest the cards under `data.data.elements[]`. Kept as a
       fallback so a LinkedIn-side shape change doesn't silently break.

    Best-effort: LinkedIn rotates decoration IDs and response shapes without
    notice, so this is not guaranteed against the live API. The included[]
    path is regression-covered by tests/test_jobs.py.
    """
    jobs: list[dict[str, Any]] = []

    # ---- Shape 1: included[] JobPostingCard entries (primary) ----
    included = data.get("included") or []
    for item in included:
        type_str = item.get("$type") or ""
        if "JobPostingCard" not in type_str:
            continue
        if not item.get("jobPostingTitle"):
            continue
        job_urn = item.get("jobPostingUrn") or item.get("entityUrn") or ""
        match = re.search(r"(\d+)", job_urn)
        job_id = match.group(1) if match else None
        jobs.append({
            "jobId": job_id,
            "title": (item.get("jobPostingTitle") or "").strip() or None,
            "company": ((item.get("primaryDescription") or {}).get("text") or "").strip() or None,
            "location": ((item.get("secondaryDescription") or {}).get("text") or "").strip() or None,
            "url": f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else None,
        })

    # ---- Shape 2 (fallback): data.elements[].jobCardUnion ----
    if not jobs:
        elements = (data.get("data") or {}).get("elements") or []
        for el in elements:
            posting = (el.get("jobCardUnion") or {}).get("jobPostingCard") or {}
            job_urn = posting.get("jobPostingUrn") or el.get("entityUrn") or ""
            match = re.search(r"(\d+)", job_urn)
            job_id = match.group(1) if match else None
            if not job_id and not posting:
                continue
            jobs.append({
                "jobId": job_id,
                "title": posting.get("jobPostingTitle") or posting.get("title"),
                "company": (posting.get("primaryDescription") or {}).get("text"),
                "location": (posting.get("secondaryDescription") or {}).get("text"),
                "url": f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else None,
            })

    paging = (data.get("data") or {}).get("paging") or {}
    return {
        "total": paging.get("total", len(jobs)),
        "jobs": jobs,
        "paging": {"start": paging.get("start", start), "count": paging.get("count", count)},
    }


async def search_jobs(
    keywords: str,
    location: str | None = None,
    workplace_type: Literal["onsite", "remote", "hybrid"] | None = None,
    job_type: Literal["fulltime", "parttime", "contract", "temporary", "internship"] | None = None,
    time_posted: Literal["past_24h", "past_week", "past_month"] | None = None,
    easy_apply: bool | None = None,
    experience_level: Literal["intern", "entry", "associate", "mid_senior", "director", "executive"] | None = None,
    start: int = 0,
    count: int = 25,
) -> dict[str, Any]:
    """
    Search LinkedIn job listings via Voyager API.

    Ported to match the verified-working TS edition
    (`src/clients/linkedin/search-jobs.ts`):
      - free-text `location` is resolved to a `geoId` (best-effort HTML scrape)
      - filters use `:List(...)` encoding (e.g. ``workplaceType:List(2)``)
      - results are parsed from `included[]` entries typed ``JobPostingCard``

    Best-effort against the live API — LinkedIn rotates decoration IDs and
    response shapes. The parser handles both the included[] shape and the
    legacy data.elements[].jobCardUnion shape.

    Returns: { total, jobs: [...], paging: { start, count, total } }
    """
    # Build :List(...) filter clauses. sortBy:List(DD) = sort by date, matches TS.
    filters: list[str] = ["sortBy:List(DD)"]
    if workplace_type and workplace_type in WORKPLACE_MAP:
        filters.append(f"workplaceType:List({WORKPLACE_MAP[workplace_type]})")
    if job_type and job_type in JOBTYPE_MAP:
        filters.append(f"jobType:List({JOBTYPE_MAP[job_type]})")
    if time_posted and time_posted in TIMEPOSTED_MAP:
        filters.append(f"timePostedRange:List({TIMEPOSTED_MAP[time_posted]})")
    if easy_apply:
        filters.append("applyWithLinkedin:List(true)")
    if experience_level and experience_level in EXPERIENCE_MAP:
        filters.append(f"experience:List({EXPERIENCE_MAP[experience_level]})")

    bounded_count = min(max(count, 1), 50)

    async with VoyagerClient() as client:
        geo_id = await _resolve_geo_id(client, location) if location else None
        query = _build_query(keywords, geo_id, filters)

        params = {
            "decorationId": DECORATION,
            "q": "jobSearch",
            "query": query,
            "start": str(start),
            "count": str(bounded_count),
        }
        data = await client.get("/voyagerJobsDashJobCards", params=params)

    return _parse_jobs(data, start, bounded_count)


async def fetch_job(job_id: str) -> dict[str, Any] | None:
    """
    Fetch a single job listing by ID.

    job_id can be a numeric ID or a full LinkedIn URL.
    """
    # Extract numeric ID from URL if needed
    match = re.search(r"(\d{6,})", job_id)
    if not match:
        return None
    numeric_id = match.group(1)

    async with VoyagerClient() as client:
        data = await client.get(
            f"/voyagerJobsDashJobPostings/urn:li:fsd_jobPosting:{numeric_id}",
            params={
                "decorationId": (
                    "com.linkedin.voyager.dash.deco.jobs.search.JobPosting-83"
                )
            },
        )

    d = data.get("data") or {}
    if not d:
        return None

    return {
        "jobId": numeric_id,
        "title": d.get("title"),
        "description": (d.get("description") or {}).get("text"),
        "companyName": (d.get("companyDetails") or {}).get("company", {}).get("name"),
        "location": d.get("formattedLocation"),
        "workplaceTypes": d.get("workplaceTypesResolutionResults"),
        "employmentStatus": d.get("formattedEmploymentStatus"),
        "experienceLevel": d.get("formattedExperienceLevel"),
        "applyUrl": (d.get("applyMethod") or {}).get("companyApplyUrl"),
        "url": f"https://www.linkedin.com/jobs/view/{numeric_id}/",
        "listedAt": d.get("listedAt"),
    }
