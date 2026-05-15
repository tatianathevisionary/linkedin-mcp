"""
LinkedIn MCP · FastMCP server.

Exposes 8 LinkedIn tools (6 ported from the TypeScript original + 2 new posts tools):

| Tool                         | Description                                                   |
|------------------------------|---------------------------------------------------------------|
| search_linkedin_jobs         | Search job listings with filters                              |
| fetch_linkedin_job           | Fetch a single job by ID                                      |
| search_linkedin_companies    | Typeahead company lookup                                      |
| fetch_linkedin_profile       | Fetch the logged-in user's full profile                       |
| fetch_linkedin_person        | Fetch any user's profile by vanity name or URL                |
| search_linkedin_people       | Search people via connections + typeahead                     |
| fetch_my_posts_from_export   | Parse a LinkedIn data export ZIP for the user's posts         |
| fetch_my_recent_activity     | Best-effort fetch via legacy Voyager (may fail · use export)  |

Auth:
- ENV VARS (production): LINKEDIN_LI_AT_COOKIE, LINKEDIN_JSESSIONID
- LOCAL macOS (fallback): Reads Chrome cookies via Keychain (pycookiecheat)

Transport:
- stdio (default)  → for Claude Code / Claude Desktop / Cursor local use
- HTTP (--http)    → for FastMCP Cloud / Docker / remote deployment

Run:
    python server.py              # stdio
    python server.py --http       # HTTP on port 8000
    fastmcp run server.py         # auto-pick transport from fastmcp.json
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Annotated, Literal, Optional

from fastmcp import FastMCP
from pydantic import Field

from linkedin import (
    fetch_job,
    fetch_my_posts_from_export,
    fetch_my_recent_activity,
    fetch_person,
    fetch_profile,
    search_companies,
    search_jobs,
    search_people,
)

# ---------- Logging ----------

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("linkedin-mcp")

# ---------- FastMCP server ----------

mcp = FastMCP(
    name="linkedin-mcp",
    instructions=(
        "Authenticated LinkedIn tools via the Voyager API + LinkedIn data export. "
        "Use search_linkedin_* for discovery, fetch_linkedin_* for full profile data, "
        "and fetch_my_posts_from_export for the user's own posts."
    ),
)


# ============================================================
# Tool 1 · Search LinkedIn jobs
# ============================================================

@mcp.tool
async def search_linkedin_jobs(
    keywords: Annotated[str, Field(description="Job title, skills, or keywords")],
    location: Annotated[Optional[str], Field(description="City, state, or region")] = None,
    workplace_type: Annotated[
        Optional[Literal["onsite", "remote", "hybrid"]],
        Field(description="Workplace arrangement filter"),
    ] = None,
    job_type: Annotated[
        Optional[Literal["fulltime", "parttime", "contract", "temporary", "internship"]],
        Field(description="Employment type filter"),
    ] = None,
    time_posted: Annotated[
        Optional[Literal["past_24h", "past_week", "past_month"]],
        Field(description="Posting recency filter"),
    ] = None,
    easy_apply: Annotated[
        Optional[bool], Field(description="Only LinkedIn Easy Apply jobs")
    ] = None,
    experience_level: Annotated[
        Optional[Literal["intern", "entry", "associate", "mid_senior", "director", "executive"]],
        Field(description="Required experience level"),
    ] = None,
    start: Annotated[int, Field(description="Pagination offset", ge=0)] = 0,
    count: Annotated[int, Field(description="Results per page (max 50)", ge=1, le=50)] = 25,
) -> dict:
    """
    Search LinkedIn job listings via the authenticated Voyager API.

    Supports filtering by workplace arrangement, employment type, posting recency,
    Easy Apply, and experience level. Returns paginated results.
    """
    return await search_jobs(
        keywords=keywords,
        location=location,
        workplace_type=workplace_type,
        job_type=job_type,
        time_posted=time_posted,
        easy_apply=easy_apply,
        experience_level=experience_level,
        start=start,
        count=count,
    )


# ============================================================
# Tool 2 · Fetch a single job
# ============================================================

@mcp.tool
async def fetch_linkedin_job(
    job_id: Annotated[str, Field(description="Job ID or full LinkedIn jobs URL")],
) -> Optional[dict]:
    """Fetch a single LinkedIn job listing by ID or URL."""
    return await fetch_job(job_id)


# ============================================================
# Tool 3 · Search companies (typeahead)
# ============================================================

@mcp.tool
async def search_linkedin_companies(
    query: Annotated[str, Field(description="Company name or keywords")],
    count: Annotated[int, Field(description="Number of results (max 50)", ge=1, le=50)] = 10,
) -> list[dict]:
    """Typeahead-style company search. Returns id, name, URL, industry, headquarters."""
    return await search_companies(query=query, count=count)


# ============================================================
# Tool 4 · Fetch the logged-in user's profile
# ============================================================

@mcp.tool
async def fetch_linkedin_profile() -> Optional[dict]:
    """
    Fetch the FULL profile of the currently logged-in LinkedIn user.

    Returns: id, firstName, lastName, headline, summary, profilePicture, profileUrl,
    location, emails, positions, education, skills, certifications, projects, languages.
    """
    return await fetch_profile()


# ============================================================
# Tool 5 · Fetch any person's profile
# ============================================================

@mcp.tool
async def fetch_linkedin_person(
    profile_input: Annotated[
        str,
        Field(description='LinkedIn vanity name (e.g. "johndoe") or full URL'),
    ],
) -> Optional[dict]:
    """Fetch any LinkedIn person's profile by vanity name or URL."""
    return await fetch_person(profile_input)


# ============================================================
# Tool 6 · Search people
# ============================================================

@mcp.tool
async def search_linkedin_people(
    keywords: Annotated[str, Field(description="Name, title, or keywords")],
    network: Annotated[
        Optional[list[Literal["1st", "2nd", "3rd"]]],
        Field(description="Connection degree filter"),
    ] = None,
    company: Annotated[Optional[str], Field(description="Current company")] = None,
    school: Annotated[Optional[str], Field(description="School attended")] = None,
    location: Annotated[Optional[str], Field(description="Geographic location")] = None,
    count: Annotated[int, Field(description="Results per page (max 50)", ge=1, le=50)] = 25,
    start: Annotated[int, Field(description="Pagination offset", ge=0)] = 0,
) -> dict:
    """Search LinkedIn people. Returns paginated results with publicIdentifier, name, headline, location, connection degree."""
    return await search_people(
        keywords=keywords,
        network=network,
        company=company,
        school=school,
        location=location,
        count=count,
        start=start,
    )


# ============================================================
# Tool 7 · Fetch posts from LinkedIn data export (PRIMARY)
# ============================================================

@mcp.tool
async def fetch_my_posts_from_export_tool(
    export_zip_path: Annotated[
        str,
        Field(description="Absolute path to the LinkedIn data export ZIP file"),
    ],
    limit: Annotated[
        Optional[int],
        Field(description="Max number of posts to return (newest first)", ge=1),
    ] = None,
) -> dict:
    """
    Parse a LinkedIn data export ZIP for the logged-in user's posts.

    To get the export:
    1. Visit https://www.linkedin.com/mypreferences/d/download-my-data
    2. Request "Posts" (or "Larger data archive" for everything)
    3. Wait ~10–30 min for LinkedIn's email
    4. Download the ZIP and pass its absolute path here

    This is the recommended path for fetching user posts — the export is
    complete, official, and future-proof. The Voyager-API path is fragile
    because LinkedIn migrated activity to a GraphQL-only path with rotating
    query hashes.
    """
    return await fetch_my_posts_from_export(export_zip_path=export_zip_path, limit=limit)


# ============================================================
# Tool 8 · Best-effort Voyager recent activity (fallback)
# ============================================================

@mcp.tool
async def fetch_my_recent_activity_tool(
    count: Annotated[int, Field(description="Number of recent posts to fetch", ge=1, le=100)] = 20,
) -> dict:
    """
    BEST-EFFORT attempt to fetch the logged-in user's recent posts via the legacy
    Voyager profileUpdatesV2 endpoint.

    This endpoint was deprecated when LinkedIn migrated to GraphQL. May return
    400/401/404. If it fails, the response includes a hint to use
    `fetch_my_posts_from_export_tool` instead.

    For reliable post data, prefer the export-based tool.
    """
    return await fetch_my_recent_activity(count=count)


# ============================================================
# Entry point
# ============================================================

def run() -> None:
    """Entry point referenced by pyproject.toml's [project.scripts]."""
    # Allow CLI flag to switch transport
    args = sys.argv[1:]
    if "--http" in args:
        port = int(os.environ.get("PORT", "8000"))
        host = os.environ.get("HOST", "0.0.0.0")
        logger.info(f"Starting LinkedIn MCP server on http://{host}:{port}/mcp/")
        mcp.run(transport="http", host=host, port=port)
    else:
        logger.info("Starting LinkedIn MCP server on stdio")
        mcp.run()


if __name__ == "__main__":
    run()
