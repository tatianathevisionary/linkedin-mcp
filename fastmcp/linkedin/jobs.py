"""Job search + single job fetch."""

from __future__ import annotations

from typing import Any, Literal, Optional

from voyager import VoyagerClient

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


async def search_jobs(
    keywords: str,
    location: Optional[str] = None,
    workplace_type: Optional[Literal["onsite", "remote", "hybrid"]] = None,
    job_type: Optional[Literal["fulltime", "parttime", "contract", "temporary", "internship"]] = None,
    time_posted: Optional[Literal["past_24h", "past_week", "past_month"]] = None,
    easy_apply: Optional[bool] = None,
    experience_level: Optional[
        Literal["intern", "entry", "associate", "mid_senior", "director", "executive"]
    ] = None,
    start: int = 0,
    count: int = 25,
) -> dict[str, Any]:
    """
    Search LinkedIn job listings via Voyager API.

    Returns: { total, jobs: [...], paging: { start, count, total } }
    """
    # Build f_* filter clauses
    filters: list[str] = []
    if workplace_type and workplace_type in WORKPLACE_MAP:
        filters.append(f"workplaceType->{WORKPLACE_MAP[workplace_type]}")
    if job_type and job_type in JOBTYPE_MAP:
        filters.append(f"jobType->{JOBTYPE_MAP[job_type]}")
    if time_posted and time_posted in TIMEPOSTED_MAP:
        filters.append(f"timePostedRange->{TIMEPOSTED_MAP[time_posted]}")
    if easy_apply:
        filters.append("applyWithLinkedin->true")
    if experience_level and experience_level in EXPERIENCE_MAP:
        filters.append(f"experience->{EXPERIENCE_MAP[experience_level]}")

    query_parts = [f"keywords:{keywords}"]
    if location:
        query_parts.append(f"locationFallback:{location}")
    if filters:
        query_parts.append(f"selectedFilters:(List({','.join(filters)}))")
    query = "(" + ",".join(query_parts) + ")"

    params = {
        "decorationId": "com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-220",
        "q": "jobSearch",
        "query": query,
        "start": str(start),
        "count": str(min(max(count, 1), 50)),
    }

    async with VoyagerClient() as client:
        data = await client.get("/voyagerJobsDashJobCards", params=data_params_to_dict(params))

    elements = data.get("data", {}).get("elements") or []
    included = data.get("included") or []

    # Build job summary entries
    jobs = []
    for el in elements:
        job_card_union = el.get("jobCardUnion") or {}
        posting = job_card_union.get("jobPostingCard") or {}
        job_urn = posting.get("jobPostingUrn") or el.get("entityUrn") or ""
        match_id = job_urn.split(":")[-1] if ":" in job_urn else None

        jobs.append({
            "jobId": match_id,
            "title": posting.get("jobPostingTitle") or posting.get("title"),
            "company": posting.get("primaryDescription", {}).get("text"),
            "location": posting.get("secondaryDescription", {}).get("text"),
            "url": f"https://www.linkedin.com/jobs/view/{match_id}/" if match_id else None,
        })

    paging = data.get("data", {}).get("paging") or {}
    return {
        "total": paging.get("total", len(jobs)),
        "jobs": jobs,
        "paging": {"start": paging.get("start", start), "count": paging.get("count", count)},
    }


async def fetch_job(job_id: str) -> Optional[dict[str, Any]]:
    """
    Fetch a single job listing by ID.

    job_id can be a numeric ID or a full LinkedIn URL.
    """
    # Extract numeric ID from URL if needed
    import re

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


def data_params_to_dict(params: dict) -> dict:
    """No-op for now; placeholder for any param coercion needed."""
    return params
