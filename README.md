# visionary-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
![MCP Server](https://img.shields.io/badge/MCP-Server-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white&style=for-the-badge)
![FastMCP](https://img.shields.io/badge/FastMCP-3.3+-green?style=for-the-badge)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3+-3178C6?logo=typescript&logoColor=white&style=for-the-badge)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin&style=for-the-badge)](https://www.linkedin.com/in/tatiana-pustovetova)

![GitHub Stars](https://img.shields.io/github/stars/tatianathevisionary/linkedin-mcp?style=social)
![GitHub Forks](https://img.shields.io/github/forks/tatianathevisionary/linkedin-mcp?style=social)
![GitHub Issues](https://img.shields.io/github/issues/tatianathevisionary/linkedin-mcp?style=social)
![Last Commit](https://img.shields.io/github/last-commit/tatianathevisionary/linkedin-mcp?style=social)

**Authenticated LinkedIn MCP server — jobs, companies, profiles, people search, and your own posts via the data export. Deployable to FastMCP Cloud in 5 minutes.**

> 🦄 **Identity-led tools for AI-native work.** Your Chrome session is the auth. Your data export is the truth. No OAuth dance, no Marketing API approval.

## What It Does

visionary-mcp is a **FastMCP 3.x server** exposing **8 authenticated LinkedIn tools** via the internal Voyager API and the official LinkedIn data export. Use it from Claude Code, Claude Desktop, Cursor, VS Code, or any MCP-compatible client.

- **Jobs**: search with workplace, type, recency, Easy Apply, and experience filters · fetch a single job by ID
- **Companies**: typeahead search returning ID, name, URL, industry, headquarters
- **Profiles**: your full profile (the logged-in user) — positions, education, skills, certifications, projects, languages
- **People**: search by keywords with connection-degree, company, school, location filters; fetch any profile by vanity name or URL
- **Posts**: parse a LinkedIn data export ZIP for your own posts (sorted newest-first, hashtags + mentions extracted)

**Deployable two ways.** Run locally over stdio for personal use, or deploy to **[Prefect Horizon](https://horizon.prefect.io)** (FastMCP Cloud) for a hosted HTTPS endpoint your agents can reach from anywhere.

## ✅ Why It's Useful

- **One MCP for the whole LinkedIn surface** — jobs, companies, profiles, people, and posts in a single server
- **Zero OAuth friction** — uses your existing Chrome login (locally) or one-time cookie env vars (production). No LinkedIn Marketing API approval needed.
- **Export-based post fetching** — when LinkedIn's posts API broke (~30 endpoint variations returning 400/401), this server pivots to the official data export. Reliable, complete, future-proof.
- **Two editions in one repo** — TypeScript for macOS/Chrome local use, Python FastMCP for production deployment. Same Voyager logic. Pick what fits.
- **Sub-60-second deploys** — push to `main`, Horizon rebuilds. Branch previews for every PR.
- **Built for the AI-native workflow** — pairs with [linkedin-os](https://github.com/tatianathevisionary/linkedin-os) for identity-led content drafting that compounds.

## 💡 Example Query

Once connected, ask your AI assistant:

> "Use visionary-mcp to fetch my full LinkedIn profile, find 10 Senior Solutions Engineer jobs at AI companies (remote, posted this week), and search for people at Anthropic with 'Forward Deployed' in their headline. Then parse my LinkedIn data export ZIP at `~/Downloads/Complete_LinkedInDataExport.zip` and surface my 5 most recent posts with hashtags + word counts."

## 📦 How to Get Started

### Option A · Connect to the Hosted Server (recommended)

Deployed at **`https://visionary-mcp.fastmcp.app/mcp`** on Prefect Horizon. Auth happens via env-var cookies set in the Horizon dashboard.

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en-US/install-mcp?name=visionary-mcp&config=eyJ1cmwiOiJodHRwczovL3Zpc2lvbmFyeS1tY3AuZmFzdG1jcC5hcHAvbWNwIn0=)

One-click install to Cursor ⤴ — opens Cursor and pre-fills the MCP config.

Or add this manually:

**For Cursor:**
```json
{
  "mcpServers": {
    "visionary-mcp": {
      "url": "https://visionary-mcp.fastmcp.app/mcp"
    }
  }
}
```

**For Claude Desktop:**
- Settings → Add Remote Server
- URL: `https://visionary-mcp.fastmcp.app/mcp`

**For VS Code:**
- Add the JSON above to your `.vscode/mcp.json`

**For Claude Code:**
```bash
claude mcp add visionary-mcp --url https://visionary-mcp.fastmcp.app/mcp
```

### Option B · Local Installation (Python FastMCP)

**Prerequisites:**
```bash
# Install UV (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Optional but recommended
uv tool install fastmcp
```

**Method 1 · One-command install**
```bash
git clone https://github.com/tatianathevisionary/linkedin-mcp.git
cd linkedin-mcp/fastmcp

fastmcp install claude-desktop server.py    # for Claude Desktop
fastmcp install cursor server.py            # for Cursor
fastmcp install claude-code server.py       # for Claude Code
```

**Method 2 · Quick run**
```bash
git clone https://github.com/tatianathevisionary/linkedin-mcp.git
cd linkedin-mcp/fastmcp
uv sync

uv run python server.py            # stdio
uv run python server.py --http     # HTTP on port 8000
```

**Method 3 · Development with inspector**
```bash
cd linkedin-mcp/fastmcp
fastmcp dev server.py
```

**Method 4 · Manual MCP config**
```json
{
  "visionary-mcp": {
    "command": "uv",
    "args": [
      "--directory",
      "/full/path/to/linkedin-mcp/fastmcp",
      "run",
      "python",
      "server.py"
    ]
  }
}
```

### Option C · TypeScript Edition (macOS local-only)

The original TypeScript edition runs over stdio with Chrome cookies via macOS Keychain. No env-var setup needed.

```bash
git clone https://github.com/tatianathevisionary/linkedin-mcp.git
cd linkedin-mcp
npm install
npm run build
node dist/server.js
```

Add to your MCP client:
```json
{
  "linkedin": {
    "type": "stdio",
    "command": "node",
    "args": ["/full/path/to/linkedin-mcp/dist/server.js"]
  }
}
```

See [`fastmcp/README.md`](./fastmcp/README.md) for the full FastMCP-edition details. See [`DEPLOY.md`](./DEPLOY.md) for the FastMCP Cloud / Docker / self-host walkthrough.

## 🛠 Available Tools (8 Total)

Every tool carries `ToolAnnotations` (`readOnlyHint`, `openWorldHint`) so MCP clients can skip confirmation prompts where safe. Each tool has typed parameters with Pydantic validation.

### Discovery (3 tools)
- **`search_linkedin_jobs`** — Voyager job search. Filters: `keywords`, `location`, `workplace_type` (onsite/remote/hybrid), `job_type` (fulltime/parttime/contract/temporary/internship), `time_posted` (past_24h/past_week/past_month), `easy_apply`, `experience_level` (intern → executive), pagination via `start` + `count`.
- **`fetch_linkedin_job`** — single job by ID or full LinkedIn jobs URL. Returns title, description, company, location, workplace types, employment status, experience level, apply URL.
- **`search_linkedin_companies`** — typeahead company lookup. Returns ID, name, URL, industry, headquarters.

### Profiles (2 tools)
- **`fetch_linkedin_profile`** — the logged-in user's full profile. Returns ID, name, headline, summary, picture, profile URL, location, emails, positions, education, skills, certifications, projects, languages.
- **`fetch_linkedin_person`** — any user's profile by vanity name (`johndoe`) or full URL (`https://linkedin.com/in/johndoe`). Returns the same shape as `fetch_linkedin_profile` plus connection degree and connections count.

### People Search (1 tool)
- **`search_linkedin_people`** — filtered people search. Filters: `keywords`, `network` (1st/2nd/3rd connection degree), `company`, `school`, `location`, pagination. Returns vanity ID, name, headline, location, profile URL, connection degree.

### Posts (2 tools)
- **`fetch_my_posts_from_export_tool`** — parses a LinkedIn data export ZIP. Reliable, official, future-proof. Returns posts sorted newest-first with hashtags, mentions, word count, visibility, URL, media URL.
- **`fetch_my_recent_activity_tool`** — best-effort fetch via the legacy Voyager `profileUpdatesV2` endpoint. LinkedIn deprecated this when they migrated activity to a GraphQL-only path with rotating query hashes, so it usually returns 400/401. Returns a structured "use export instead" hint when the endpoint fails.

## 🚀 Deployment

### Deploy to Prefect Horizon (FastMCP Cloud) — 5 minutes

1. **Sign in** at [horizon.prefect.io](https://horizon.prefect.io) with your GitHub account
2. **Click "+ New server"** on your servers page
3. **Authorize Prefect Horizon** for your GitHub repos (one-time)
4. **Pick the repo**: `tatianathevisionary/linkedin-mcp`
5. **Configure**:
   - **Server name**: `visionary-mcp`
   - **Branch**: `main`
   - **Entrypoint**: `fastmcp/server.py:mcp`
   - **Python version**: `3.12` (or `3.11`)
   - **Authentication**: off (private use)
6. **Add environment variables** (one per line, `KEY=value` format):
   ```
   LINKEDIN_LI_AT_COOKIE=<paste your li_at value from Chrome DevTools>
   LINKEDIN_JSESSIONID=<paste your JSESSIONID value, keep the quotes>
   ```
7. **Click Deploy**. Wait ~60 seconds.
8. **Done.** Your URL: `https://visionary-mcp.fastmcp.app/mcp`

**Auto-redeploy**: every push to `main` triggers a rebuild. Preview deployments for every PR.

### How to grab cookie values

1. Open Chrome → log into LinkedIn
2. DevTools (`Cmd+Option+I` on macOS) → **Application** tab → **Cookies** → `https://www.linkedin.com`
3. Copy the **Value** column for `li_at` (no surrounding quotes)
4. Copy the **Value** column for `JSESSIONID` (looks like `"ajax:1234..."` — **keep the quotes**)
5. These cookies last ~12 months. Rotate via the Horizon dashboard when LinkedIn logs you out.

### Other deployment paths

| Platform | How |
|---|---|
| **Docker** | `cd fastmcp && docker build -t visionary-mcp . && docker run -p 8000:8000 -e LINKEDIN_LI_AT_COOKIE=... visionary-mcp` |
| **Cloud Run** | `gcloud run deploy visionary-mcp --source ./fastmcp --set-env-vars LINKEDIN_LI_AT_COOKIE=...` |
| **Fly.io** | `cd fastmcp && fly launch --no-deploy && fly secrets set LINKEDIN_LI_AT_COOKIE=... && fly deploy` |
| **Render** | New Web Service → root directory `fastmcp` → build `pip install -e .` → start `python server.py --http` |

Full walkthroughs in [`DEPLOY.md`](./DEPLOY.md).

## ⚡ Key Features

- **8 LinkedIn tools** spanning jobs, companies, profiles, people, and posts
- **Two editions in one repo**: TypeScript (stdio · macOS Chrome cookies) + Python FastMCP (stdio/HTTP/SSE · env-var auth · cloud-deployable)
- **Voyager API + data export hybrid** — uses LinkedIn's internal API where it works, falls back to the official data export where the API broke
- **Pydantic-validated parameters** — typed schemas with autocomplete in any MCP client
- **macOS Keychain cookie reading** (TS + Python fallback) via `keytar` / `pycookiecheat`
- **Async HTTP via `httpx`** — concurrent-safe, timeout-controlled
- **CSRF token handling** — auto-extracts from JSESSIONID cookie per LinkedIn convention
- **Profile entity parsing** — handles 7+ LinkedIn profile sub-types (Position, Education, Skill, Certification, Project, Language, NetworkInfo)
- **Post normalization** — extracts hashtags, @-mentions, word counts, media types from export CSV
- **36/36 pytest tests passing** — parsers, posts export, auth helpers covered
- **GitHub Actions CI** — Python 3.11 + 3.12 matrix · Docker build verification
- **MIT License** — fork it, sell it, modify it, just don't claim someone else's identity as your own

## 🔐 Authentication

Unlike most MCP servers, this one **requires LinkedIn auth.** Two modes, auto-detected:

| Mode | When | What's needed |
|---|---|---|
| **Env vars** (production) | Horizon · Docker · any deployed server | `LINKEDIN_LI_AT_COOKIE` + `LINKEDIN_JSESSIONID` |
| **Chrome cookies** (local) | macOS dev with Chrome logged into LinkedIn | Nothing — `pycookiecheat` / `keytar` reads via Keychain |

### Why no OAuth?

LinkedIn's Marketing Developer Platform requires app approval (weeks-to-months), real business justification, and limits you to a narrow subset of endpoints. For personal use + small teams, cookie-based auth is the only practical path.

### Risks + mitigations

- ⚠️ **Cookies expire ~12 months** — rotate when LinkedIn logs you out
- ⚠️ **Rate limits** — keep volume reasonable (under ~100 req per 15 min per cookie session)
- ⚠️ **Cookies are passwords** — treat them like secrets. The `.gitignore` blocks `.env` files
- ✅ **Per-account scope** — your cookies = your account. LinkedIn can't take down a Horizon URL; worst case is your account gets rate-limited

## 💬 FAQ

<details>
<summary><strong>Why two editions (TypeScript + Python)?</strong></summary>

The TypeScript edition predates this repo's FastMCP version. It works great for local macOS use over stdio, reads Chrome cookies via Keychain, and runs as a Node process. The Python FastMCP edition adds HTTP transport, env-var auth, and deployability to FastMCP Cloud / Docker / any HTTP host. Both run side-by-side and share the same Voyager logic.
</details>

<details>
<summary><strong>Will this get my LinkedIn account banned?</strong></summary>

Not in normal personal use. Cookie-based auth ties to your account, so worst case is LinkedIn rate-limits your IP or revokes the cookie (you re-login + grab a fresh one). The server doesn't do anything automated by default — it only responds to your MCP-client calls. High-frequency automated abuse is what triggers bans; manual research, profile fetches, and occasional post pulls don't.
</details>

<details>
<summary><strong>The Voyager `fetch_my_recent_activity_tool` returns an error. Why?</strong></summary>

LinkedIn migrated member activity to a GraphQL-only path with rotating SHA-256 query hashes that change weekly. The legacy `profileUpdatesV2` endpoint we'd love to use returns 400/401. The reliable workaround is **`fetch_my_posts_from_export_tool`** — parse the official LinkedIn data export ZIP. It's complete, future-proof, and gives you every post you've ever made.
</details>

<details>
<summary><strong>How do I get the LinkedIn data export?</strong></summary>

1. <https://www.linkedin.com/mypreferences/d/download-my-data>
2. Pick "Posts" (or "Larger data archive" for everything)
3. Wait ~10–30 min for LinkedIn's email
4. Download the ZIP
5. Pass its absolute path to `fetch_my_posts_from_export_tool`

The tool parses `Shares.csv`, normalizes dates, extracts hashtags + mentions, sorts newest-first.
</details>

<details>
<summary><strong>Can multiple users share one Horizon deployment?</strong></summary>

Not safely — the deployment uses one set of env-var cookies, so every caller authenticates as YOUR LinkedIn account. For multi-user deployments, you'd need to refactor to accept per-request cookie headers (not currently supported). For now, deploy one Horizon server per user.
</details>

<details>
<summary><strong>What MCP clients work?</strong></summary>

Anything that speaks MCP: Claude Desktop, Claude Code, Cursor, VS Code (with the MCP extension), Goose, Gemini CLI, custom FastMCP clients. The hosted server is HTTP-transport; the local edition supports stdio.
</details>

<details>
<summary><strong>Does this work on Linux / Windows?</strong></summary>

Yes — when running with env-var auth. The Chrome-cookie fallback is macOS-only (depends on `keytar` / Keychain). Linux and Windows users should set `LINKEDIN_LI_AT_COOKIE` + `LINKEDIN_JSESSIONID` env vars.
</details>

<details>
<summary><strong>Is this open source?</strong></summary>

Yes — MIT licensed. Fork, modify, sell, just don't claim someone else's identity as your own. See [`LICENSE`](./LICENSE).
</details>

## 🤝 Contributing

Contributions are welcome — bug fixes, new LinkedIn endpoints, better post parsers, additional MCP client integrations.

1. **Fork the Project**
2. **Create your Feature Branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your Changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the Branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

## 💡 Issues, Feedback & Support

Found a bug, have a feature request, or building something interesting on top of this?

- **Report a bug** — broken parser · new LinkedIn endpoint behavior · deployment friction
- **Request a feature** — new tools · better post analysis · multi-user auth
- **Share your use case** — what are you building?

👉 **[Open an Issue](https://github.com/tatianathevisionary/linkedin-mcp/issues)**

## Related

- **[linkedin-os](https://github.com/tatianathevisionary/linkedin-os)** — identity-led LinkedIn content operating system. Pairs with this MCP to give your AI agent both *who you are* and *what's on your LinkedIn*.
- **[fastmcp](https://gofastmcp.com)** — the framework powering the Python edition
- **[Prefect Horizon](https://horizon.prefect.io)** — the hosted deployment platform

## Attribution & License

Open source under the **MIT License**. If you use visionary-mcp, please credit it by linking back to [visionary-mcp](https://github.com/tatianathevisionary/linkedin-mcp). See [LICENSE](LICENSE) for details.

## ⭐ Like this project? Give it a star!

If visionary-mcp is useful for your AI-native workflow, please consider giving it a star. It helps others discover the project.

[![Star this repo](https://img.shields.io/github/stars/tatianathevisionary/linkedin-mcp?style=social)](https://github.com/tatianathevisionary/linkedin-mcp)

---

> 🦄 *"AI is the medium I work in. Not a tool I borrow. I'm not a user; I am an author."*
>
> Built in Calgary by [Tatiana Pustovetova](https://tatianathevisionary.com). 💜
