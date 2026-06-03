"""
Posts tools.

Two paths to user posts:

1. `fetch_my_posts_from_export(zip_path)` — PRIMARY
   Parses the official LinkedIn data export ZIP. Most complete + future-proof.
   To get the export: https://www.linkedin.com/mypreferences/d/download-my-data

2. `fetch_my_recent_activity(count)` — BEST-EFFORT
   Attempts the legacy Voyager profileUpdatesV2 endpoint. LinkedIn migrated
   member activity to GraphQL with rotating query hashes, so this often
   returns 400/401. Falls back gracefully with a hint to use the export path.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voyager import VoyagerClient, VoyagerError, extract_hashtags, extract_mentions

logger = logging.getLogger(__name__)


# ---------- Export-based path (PRIMARY) ----------

POSTS_FILES = ["Shares.csv", "shares.csv", "Member_Shares.csv"]
COMMENTS_FILES = ["Comments.csv", "comments.csv"]
REACTIONS_FILES = ["Reactions.csv", "reactions.csv"]


async def fetch_my_posts_from_export(
    export_zip_path: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Parse the LinkedIn data export ZIP and return normalized posts.

    To get the export:
    1. Visit https://www.linkedin.com/mypreferences/d/download-my-data
    2. Request "Posts" (or "Larger data archive" for everything)
    3. Wait for LinkedIn's email (~10–30 min)
    4. Download the ZIP and pass its absolute path to this tool

    Returns:
    {
        "total": int,
        "posts": [{date, text, url, mediaUrl, visibility, hashtags, mentions, ...}],
        "fetchedAt": iso8601,
        "source": "linkedin-data-export"
    }
    """
    path = Path(export_zip_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Export ZIP not found: {path}")

    posts: list[dict[str, Any]] = []

    with zipfile.ZipFile(path, "r") as zf:
        # Find Shares CSV
        shares_name = next(
            (name for name in zf.namelist() if any(name.endswith(f) for f in POSTS_FILES)),
            None,
        )
        if not shares_name:
            raise ValueError(
                f"Could not find a Shares CSV in {path}. "
                f"Expected one of: {POSTS_FILES}. "
                f"Make sure you requested 'Posts' (not just connections) when exporting."
            )

        with zf.open(shares_name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text)
            for row in reader:
                # Schema varies slightly across LinkedIn export versions.
                # Try multiple field name variants.
                date_str = (
                    row.get("Date")
                    or row.get("date")
                    or row.get("SharedAt")
                    or row.get("Shared Date")
                )
                share_text = (
                    row.get("ShareCommentary")
                    or row.get("Share Commentary")
                    or row.get("ShareText")
                    or row.get("Text")
                    or ""
                )
                visibility = (
                    row.get("Visibility")
                    or row.get("visibility")
                    or row.get("ShareVisibility")
                )
                share_link = (
                    row.get("ShareLink")
                    or row.get("Share Link")
                    or row.get("URL")
                    or row.get("Share URL")
                )
                media_url = (
                    row.get("MediaUrl")
                    or row.get("Media URL")
                    or row.get("SharedUrl")
                )

                posts.append({
                    "date": _normalize_date(date_str),
                    "text": share_text.strip(),
                    "textLength": len(share_text),
                    "url": share_link or None,
                    "mediaUrl": media_url or None,
                    "visibility": visibility or None,
                    "hashtags": extract_hashtags(share_text),
                    "mentions": extract_mentions(share_text),
                    "wordCount": len(share_text.split()),
                })

    # Sort newest first
    posts.sort(key=lambda p: p.get("date") or "", reverse=True)

    if limit:
        posts = posts[:limit]

    return {
        "total": len(posts),
        "posts": posts,
        "fetchedAt": datetime.now(UTC).isoformat(),
        "source": "linkedin-data-export",
    }


def _normalize_date(date_str: str | None) -> str | None:
    """Normalize LinkedIn export date strings to ISO 8601."""
    if not date_str:
        return None
    # LinkedIn export uses "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD HH:MM:SS UTC"
    cleaned = date_str.strip().replace(" UTC", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(cleaned, fmt).replace(tzinfo=UTC)
            return dt.isoformat()
        except ValueError:
            continue
    return cleaned  # return raw if we can't parse


# ---------- Voyager-based path (BEST-EFFORT) ----------

EXPORT_HINT = (
    "LinkedIn migrated member activity to a GraphQL-only path with rotating query "
    "hashes. The legacy profileUpdatesV2 endpoint no longer works reliably. "
    "Use `fetch_my_posts_from_export` with a LinkedIn data export ZIP instead. "
    "Request the export at https://www.linkedin.com/mypreferences/d/download-my-data."
)


async def fetch_my_recent_activity(count: int = 20) -> dict[str, Any]:
    """
    BEST-EFFORT attempt to fetch the logged-in user's recent posts via the
    legacy Voyager profileUpdatesV2 endpoint.

    This endpoint was deprecated when LinkedIn migrated activity to GraphQL.
    Returns posts if the endpoint still works for the current account, OR
    a structured "use export instead" response otherwise.

    For reliable post fetching, use `fetch_my_posts_from_export`.
    """
    async with VoyagerClient() as client:
        # Resolve own profile URN
        try:
            prefs = await client.get(
                "/voyagerJobsDashJobSeekerPreferences",
                params={
                    "decorationId": "com.linkedin.voyager.dash.deco.jobs.FullJobSeekerPreference-8"
                },
            )
            entity_urn = (prefs.get("data") or {}).get("entityUrn") or ""
            match = re.search(r"ACo[A-Za-z0-9_-]+", entity_urn)
            if not match:
                return {
                    "error": "Could not resolve own profile URN",
                    "hint": EXPORT_HINT,
                    "source": "voyager-failed",
                }
            profile_urn = match.group(0)
        except VoyagerError as e:
            return {
                "error": f"Voyager auth check failed: {e.message}",
                "hint": EXPORT_HINT,
                "source": "voyager-failed",
            }

        # Try the legacy endpoint
        try:
            data = await client.get(
                "/identity/profileUpdatesV2",
                params={
                    "profileId": profile_urn,
                    "q": "memberShareFeed",
                    "moduleKey": "member-shares:phone",
                    "count": str(min(max(count, 1), 100)),
                    "includeLongTermHistory": "true",
                },
            )
        except VoyagerError as e:
            return {
                "error": f"Voyager profileUpdatesV2 endpoint returned {e.status}: {e.message}",
                "hint": EXPORT_HINT,
                "source": "voyager-failed",
                "fallback_path": "fetch_my_posts_from_export",
            }

        elements = data.get("elements") or (data.get("data") or {}).get("elements") or []
        included = data.get("included") or []

        posts = [
            _parse_share(el.get("value", {}).get("com.linkedin.voyager.feed.render.UpdateV2", el.get("value", el)), included)
            for el in elements
        ]
        posts = [p for p in posts if p]

        return {
            "total": len(posts),
            "posts": posts,
            "fetchedAt": datetime.now(UTC).isoformat(),
            "source": "voyager-profileUpdatesV2",
            "warning": (
                "This endpoint is deprecated. Engagement counts may be missing or "
                "stale. Use fetch_my_posts_from_export for reliable post data."
            ),
        }


def _parse_share(share: dict[str, Any], included: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Parse a Voyager share/update element into a normalized post."""
    urn = share.get("urn") or share.get("entityUrn") or share.get("dashEntityUrn") or ""
    if not urn:
        return None

    commentary = share.get("commentary") or {}
    text_obj = commentary.get("text") or {}
    text = (text_obj.get("text") if isinstance(text_obj, dict) else text_obj) or ""

    # Engagement counts
    social = share.get("socialDetail") or (share.get("updateMetadata") or {}).get("socialDetail") or {}
    counts = social.get("totalSocialActivityCounts") or {}
    reactions = _safe_int(counts.get("numLikes") or counts.get("numReactions"))
    comments = _safe_int(counts.get("numComments"))
    reposts = _safe_int(counts.get("numShares"))

    # Permalink
    permalink = share.get("permalink")
    if not permalink:
        activity_match = re.search(r"activity:(\d+)", urn)
        if activity_match:
            permalink = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_match.group(1)}/"

    return {
        "urn": urn,
        "permalink": permalink,
        "text": text,
        "textLength": len(text),
        "isRepost": bool(share.get("resharedUpdate") or share.get("resharedUpdateUrn")),
        "engagement": {
            "reactions": reactions,
            "comments": comments,
            "reposts": reposts,
        },
        "hashtags": extract_hashtags(text),
        "mentions": extract_mentions(text),
    }


def _safe_int(v: Any) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            return 0
    return 0
