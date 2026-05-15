# linkedin-mcp

> **Two MCP servers exposing authenticated LinkedIn tools.** Pick the edition that fits.

| Edition | Language | Transport | Auth | Deployable | Where |
|---------|----------|-----------|------|------------|-------|
| Original | TypeScript | stdio | Chrome cookies via macOS Keychain | Local only | `./` (root) |
| **FastMCP** | Python | stdio · HTTP · SSE | Env vars (prod) + Chrome (local) | FastMCP Cloud · Docker · anywhere | [`./fastmcp/`](./fastmcp/) |

Both run the same Voyager API logic. Both are MIT-licensed. Both support the same 6 base tools — the FastMCP edition adds 2 more for posts.

---

## 🛠️ Tools

| Tool | TS | FastMCP |
|------|----|---------|
| `search_linkedin_jobs` | ✅ | ✅ |
| `fetch_linkedin_job` | ✅ | ✅ |
| `search_linkedin_companies` | ✅ | ✅ |
| `fetch_linkedin_profile` | ✅ | ✅ |
| `fetch_linkedin_person` | ✅ | ✅ |
| `search_linkedin_people` | ✅ | ✅ |
| `fetch_my_posts_from_export_tool` | ❌ | ✅ **NEW** |
| `fetch_my_recent_activity_tool` | ⚠️ broken | ✅ **NEW** (best-effort) |

---

## 🚀 Pick your path

### Quick local use (macOS, Chrome session)
→ Use the **TypeScript edition**. See instructions below.

### Production / remote / multi-platform
→ Use the **FastMCP edition** in [`./fastmcp/`](./fastmcp/). See [`DEPLOY.md`](./DEPLOY.md).

---

## TypeScript edition (legacy · still working)

Self-contained MCP server exposing 6 authenticated LinkedIn tools via the Voyager API. Reuses the active Chrome session cookies on macOS — no manual OAuth, no API keys.

### Requirements
- macOS (reads Chrome cookies via Keychain)
- Logged into LinkedIn in Google Chrome
- Node 20+ with `npx`

### Install
```bash
npm install
npm run build
```

### Run
```bash
node dist/server.js
```

### Wire into Claude Code
```json
{
  "mcpServers": {
    "linkedin": {
      "type": "stdio",
      "command": "node",
      "args": ["/absolute/path/to/linkedin-mcp/dist/server.js"]
    }
  }
}
```

### Per-tool CLIs
```bash
npm run linkedin:profile     # your own profile
npm run linkedin:person -- "vanity-name"
npm run linkedin:companies -- "company name"
npm run linkedin:people -- "search keywords"
npm run linkedin:search -- "job keywords"
npm run linkedin:job -- "job-id-or-url"
```

---

## FastMCP edition (production-ready · recommended)

See [`./fastmcp/README.md`](./fastmcp/README.md) for full docs.

### TL;DR

```bash
cd fastmcp
uv sync
uv run python server.py             # stdio mode
uv run python server.py --http      # HTTP mode on port 8000
```

### Deploy to FastMCP Cloud

```bash
gh repo create tatianathevisionary/linkedin-mcp --private --source . --push
# Then visit https://fastmcp.app → Connect GitHub → deploy
```

See [`./DEPLOY.md`](./DEPLOY.md) for the full walkthrough (FastMCP Cloud, Docker, Cloud Run, Fly.io, Render).

---

## 📜 License

MIT. See [`./LICENSE`](./LICENSE).

---

## Related

- **[linkedin-os](https://github.com/tatianathevisionary/linkedin-os)** · the identity-led LinkedIn content system that uses this MCP
- **linkedin-agent** · the companion agent built on this MCP (sibling folder)
