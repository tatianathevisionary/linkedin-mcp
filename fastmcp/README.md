# linkedin-mcp · FastMCP Python edition

> **Production-grade LinkedIn MCP server. Deploys to FastMCP Cloud, Docker, or runs locally over stdio.**

The Python rewrite of the [LinkedIn MCP](../README.md) — built on FastMCP 3.x for production deployment.

| | TypeScript edition | **FastMCP edition (this folder)** |
|---|---|---|
| Transport | stdio only | stdio · HTTP · SSE |
| Auth | Chrome cookies via Keychain (macOS) | Env vars (production) + Chrome fallback (local) |
| Deployment | Local only | FastMCP Cloud · Docker · any HTTP host |
| Posts support | Best-effort (legacy endpoint) | Export-based (reliable) + best-effort fallback |
| Tools | 6 | 8 (6 + 2 posts) |

---

## 🛠️ Tools

| Tool | What it does |
|------|--------------|
| `search_linkedin_jobs` | Job search with workplace, type, recency, Easy Apply, experience filters |
| `fetch_linkedin_job` | Single job by ID or URL |
| `search_linkedin_companies` | Typeahead company lookup |
| `fetch_linkedin_profile` | YOUR full profile (logged-in user) |
| `fetch_linkedin_person` | Any user's profile by vanity name or URL |
| `search_linkedin_people` | People search with connection-degree, company, school, location filters |
| `fetch_my_posts_from_export_tool` | **Parse LinkedIn data export ZIP** (recommended for posts) |
| `fetch_my_recent_activity_tool` | Best-effort Voyager fallback for posts |

---

## 🚀 Quick start

### Local (stdio)

```bash
cd fastmcp
uv sync
uv run python server.py
```

Wire into Claude Code via `.mcp.json` (see project root).

### Local (HTTP)

```bash
cd fastmcp
uv run python server.py --http
# server listens on http://0.0.0.0:8000/mcp/
```

### Docker

```bash
cd fastmcp
docker build -t linkedin-mcp .
docker run -p 8000:8000 \
  -e LINKEDIN_LI_AT_COOKIE=... \
  -e LINKEDIN_JSESSIONID=... \
  linkedin-mcp
```

### FastMCP Cloud (one-click deploy)

1. Push this repo to GitHub
2. Visit <https://fastmcp.app> → Connect GitHub → pick `tatianathevisionary/linkedin-mcp`
3. FastMCP reads `fastmcp.json` and deploys automatically
4. Set `LINKEDIN_LI_AT_COOKIE` and `LINKEDIN_JSESSIONID` as secrets in the FastMCP dashboard
5. Get your deployment URL: `https://linkedin-mcp.fastmcp.app/mcp`
6. Add to any MCP-aware client:

```json
{
  "mcpServers": {
    "linkedin": {
      "url": "https://linkedin-mcp.fastmcp.app/mcp"
    }
  }
}
```

See [`DEPLOY.md`](../DEPLOY.md) for the full deployment walkthrough.

---

## 🔐 Authentication

Two modes, auto-detected:

### Production · env vars (recommended for deployed servers)

Set these on your hosting platform:

```bash
export LINKEDIN_LI_AT_COOKIE=...     # the `li_at` cookie value from Chrome DevTools
export LINKEDIN_JSESSIONID=...       # the `JSESSIONID` cookie value (keep the quotes)
```

How to get them:
1. Log into LinkedIn in Chrome
2. DevTools → Application → Cookies → `https://www.linkedin.com`
3. Copy `li_at` and `JSESSIONID` values

These cookies last ~12 months. Rotate when LinkedIn logs you out.

### Local · Chrome session (no setup)

If env vars aren't set, the server falls back to reading Chrome's cookie store via macOS Keychain (`pycookiecheat`). No-op on Linux/Windows.

---

## 📦 Posts: the export-based path

LinkedIn deprecated the public posts API. The reliable path is the data export:

1. Visit <https://www.linkedin.com/mypreferences/d/download-my-data>
2. Pick "Posts" (or "Larger data archive")
3. Wait 10–30 min for LinkedIn's email
4. Download the ZIP
5. Pass its absolute path to `fetch_my_posts_from_export_tool`

The tool parses `Shares.csv`, normalizes dates, extracts hashtags + mentions, returns sorted-newest-first JSON.

---

## 🧪 Tests

```bash
cd fastmcp
uv run pytest -v
```

CI runs on Python 3.11 + 3.12 via GitHub Actions (see `.github/workflows/ci.yml`).

---

## 📂 Layout

```
fastmcp/
├── server.py              FastMCP entry point · @mcp.tool decorators
├── auth.py                Cookie loading (env vars + Chrome fallback)
├── voyager.py             Async HTTP client for Voyager API
├── linkedin/
│   ├── __init__.py
│   ├── parsers.py         Shared profile entity parsers
│   ├── profile.py         fetch_profile · fetch_person
│   ├── jobs.py            search_jobs · fetch_job
│   ├── companies.py       search_companies
│   ├── people.py          search_people
│   └── posts.py           fetch_my_posts_from_export · fetch_my_recent_activity
├── tests/
│   ├── test_parsers.py
│   ├── test_posts_export.py
│   └── test_auth.py
├── .github/workflows/
│   └── ci.yml
├── pyproject.toml         UV-managed deps
├── fastmcp.json           FastMCP deployment config
├── Dockerfile             Production container
├── .env.example
├── .gitignore
└── README.md
```

---

## 🤝 Sibling: TypeScript edition

The original TypeScript edition lives one folder up at [`../`](../). It uses
Chrome cookies on macOS only (no env-var auth) and is stdio-only.

Both editions can run side-by-side. Pick:

- **TypeScript** if you only need local stdio use with a macOS Chrome login
- **FastMCP** if you want HTTP transport, remote deployment, env-var auth, or the export-based posts tool

---

## 📜 License

MIT. See [`../LICENSE`](../LICENSE).
