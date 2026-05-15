"""
LinkedIn auth · cookie loading.

Two modes:
1. ENV VAR mode (production / FastMCP Cloud / Docker) — uses LINKEDIN_LI_AT_COOKIE
   and LINKEDIN_JSESSIONID env vars.
2. CHROME mode (local dev on macOS) — falls back to reading active Chrome
   session cookies via Keychain using pycookiecheat.

The Voyager API needs both:
- `li_at` cookie (authentication)
- `JSESSIONID` cookie (CSRF token — extracted via 'csrf-token' header)
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

LINKEDIN_DOMAIN = "https://www.linkedin.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class LinkedInAuth:
    """Holds the auth state needed for Voyager API calls."""

    li_at: str
    jsessionid: str
    cookie_header: str
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def csrf_token(self) -> str:
        """Extract csrf-token from JSESSIONID (LinkedIn convention)."""
        return self.jsessionid.strip('"')

    def headers(self, accept: str = "application/vnd.linkedin.normalized+json+2.1") -> dict[str, str]:
        """Standard Voyager API request headers."""
        return {
            "Cookie": self.cookie_header,
            "csrf-token": self.csrf_token,
            "User-Agent": self.user_agent,
            "Accept": accept,
            "X-Restli-Protocol-Version": "2.0.0",
            "X-Li-Lang": "en_US",
            "Referer": "https://www.linkedin.com/feed/",
        }


def _build_cookie_header(li_at: str, jsessionid: str, extras: Optional[dict[str, str]] = None) -> str:
    """Build a Cookie header string from individual cookie values."""
    parts = [f"li_at={li_at}", f'JSESSIONID="{jsessionid.strip(chr(34))}"']
    if extras:
        for k, v in extras.items():
            parts.append(f"{k}={v}")
    return "; ".join(parts)


def load_from_env() -> Optional[LinkedInAuth]:
    """Load auth from environment variables. Returns None if either is missing."""
    li_at = os.environ.get("LINKEDIN_LI_AT_COOKIE")
    jsessionid = os.environ.get("LINKEDIN_JSESSIONID")

    if not li_at or not jsessionid:
        return None

    user_agent = os.environ.get("LINKEDIN_USER_AGENT", DEFAULT_USER_AGENT)
    cookie_header = _build_cookie_header(li_at, jsessionid)

    logger.info("Loaded LinkedIn auth from environment variables")
    return LinkedInAuth(
        li_at=li_at,
        jsessionid=jsessionid,
        cookie_header=cookie_header,
        user_agent=user_agent,
    )


def load_from_chrome() -> Optional[LinkedInAuth]:
    """
    Load auth from local Chrome session (macOS only).

    Uses pycookiecheat to read the Chrome cookie SQLite DB and decrypt via Keychain.
    Returns None if not on macOS, pycookiecheat unavailable, or no LinkedIn session.
    """
    if sys.platform != "darwin":
        logger.debug("Chrome cookie fallback only supported on macOS")
        return None

    try:
        from pycookiecheat import chrome_cookies
    except ImportError:
        logger.warning("pycookiecheat not installed — install with `pip install pycookiecheat`")
        return None

    try:
        cookies = chrome_cookies(LINKEDIN_DOMAIN, browser="Chrome")
    except Exception as e:
        logger.warning(f"Failed to read Chrome cookies: {e}")
        return None

    li_at = cookies.get("li_at")
    jsessionid = cookies.get("JSESSIONID")

    if not li_at or not jsessionid:
        logger.warning(
            "Could not find li_at and JSESSIONID in Chrome cookies. "
            "Make sure you're logged into LinkedIn in Chrome."
        )
        return None

    # Pass through any other cookies that may help (e.g., lang, bcookie)
    extras = {k: v for k, v in cookies.items() if k not in ("li_at", "JSESSIONID")}
    cookie_header = _build_cookie_header(li_at, jsessionid, extras=extras)

    logger.info("Loaded LinkedIn auth from local Chrome session")
    return LinkedInAuth(
        li_at=li_at,
        jsessionid=jsessionid,
        cookie_header=cookie_header,
    )


def load_auth() -> LinkedInAuth:
    """
    Load LinkedIn auth via env vars (production) or Chrome cookies (local).

    Raises RuntimeError if neither mode produces valid credentials.
    """
    auth = load_from_env() or load_from_chrome()
    if auth is None:
        raise RuntimeError(
            "Could not load LinkedIn auth. Set LINKEDIN_LI_AT_COOKIE and "
            "LINKEDIN_JSESSIONID env vars, OR log into LinkedIn in Chrome "
            "on macOS (the server reads Chrome's cookie store via Keychain)."
        )
    return auth
