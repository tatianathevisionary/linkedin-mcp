# Deploy · linkedin-mcp

Three deployment paths, ranked by ease.

---

## 🟢 Path 1 · FastMCP Cloud (recommended)

Zero-infra. Push to GitHub, connect, deploy. ~5 minutes.

### Steps

1. **Push the repo to GitHub**

   ```bash
   cd /Users/tatianathevisionary/Documents/building-tatianathevisionary/linkedin-mcp
   gh repo create tatianathevisionary/linkedin-mcp --private --source . --push
   ```

2. **Sign in to FastMCP Cloud**: <https://fastmcp.app>

3. **Connect GitHub** and authorize access to `tatianathevisionary/linkedin-mcp`

4. **Create deployment** → select the repo + branch `main`
   - FastMCP auto-detects `fastmcp/fastmcp.json`
   - Builds with `uv sync` using `fastmcp/pyproject.toml`
   - Runs `python server.py --http` on port 8000

5. **Set secrets** in the FastMCP dashboard:
   - `LINKEDIN_LI_AT_COOKIE` → your `li_at` cookie from Chrome DevTools
   - `LINKEDIN_JSESSIONID` → your `JSESSIONID` cookie (keep the quotes)

6. **Deploy** → wait ~2 min for build + start

7. **Get your URL**: `https://linkedin-mcp.fastmcp.app/mcp` (or whatever name you chose)

8. **Wire into your MCP client**:

   ```json
   {
     "mcpServers": {
       "linkedin": {
         "url": "https://linkedin-mcp.fastmcp.app/mcp"
       }
     }
   }
   ```

### Updating

Push to `main` → FastMCP rebuilds + redeploys automatically.

### Cost

FastMCP Cloud free tier covers personal use. Check current pricing at fastmcp.app.

---

## 🟡 Path 2 · Docker (any host)

For Cloud Run, Fly.io, Railway, Render, AWS App Runner, or your own VPS.

### Build locally

```bash
cd fastmcp
docker build -t linkedin-mcp:latest .
```

### Run locally

```bash
docker run -p 8000:8000 \
  -e LINKEDIN_LI_AT_COOKIE="your_li_at" \
  -e LINKEDIN_JSESSIONID='"your_jsessionid_with_quotes"' \
  linkedin-mcp:latest
```

Verify it's running:
```bash
curl http://localhost:8000/mcp/
```

### Deploy to Fly.io (example)

```bash
cd fastmcp
fly launch --no-deploy            # creates fly.toml
fly secrets set LINKEDIN_LI_AT_COOKIE=... LINKEDIN_JSESSIONID=...
fly deploy
```

### Deploy to Cloud Run (example)

```bash
gcloud run deploy linkedin-mcp \
  --source ./fastmcp \
  --region us-central1 \
  --set-env-vars LINKEDIN_LI_AT_COOKIE=...,LINKEDIN_JSESSIONID=...
```

### Deploy to Render (example)

1. New Web Service → connect GitHub
2. Root directory: `fastmcp`
3. Build command: `pip install -e .`
4. Start command: `python server.py --http`
5. Env vars: `LINKEDIN_LI_AT_COOKIE`, `LINKEDIN_JSESSIONID`

---

## 🔵 Path 3 · Local stdio (no deployment)

For Claude Code / Claude Desktop / Cursor running on your machine.

```bash
cd fastmcp
uv sync
```

Then add to your MCP client config:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/linkedin-mcp/fastmcp", "run", "python", "server.py"]
    }
  }
}
```

**Claude Code** (`~/.claude.json` or per-project `.mcp.json`):
```json
{
  "mcpServers": {
    "linkedin": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/linkedin-mcp/fastmcp", "run", "python", "server.py"]
    }
  }
}
```

Auth happens via local Chrome cookies — no env vars needed on macOS.

---

## 🔐 Auth notes

| Mode | When to use | What's needed |
|------|-------------|---------------|
| Env vars | Production · Docker · FastMCP Cloud | `LINKEDIN_LI_AT_COOKIE` + `LINKEDIN_JSESSIONID` |
| Chrome cookies | Local macOS development | Just stay logged into LinkedIn in Chrome |

### How to get cookie values

1. Open Chrome → log into LinkedIn
2. DevTools (Cmd+Option+I) → Application → Cookies → `https://www.linkedin.com`
3. Copy `li_at` and `JSESSIONID` values
4. **`JSESSIONID` is wrapped in quotes** in the cookie store — keep those quotes in the env var

### Cookie rotation

LinkedIn cookies last ~12 months. When they expire (or LinkedIn logs you out):
1. Get fresh values from DevTools
2. Update the secret on your hosting platform
3. Redeploy (or wait for the running container to pick up the new env via restart)

---

## 🧪 Health check

After deploy, verify the server responds:

```bash
# Should return MCP server metadata
curl https://linkedin-mcp.fastmcp.app/mcp/

# Test a tool via the MCP inspector
fastmcp dev https://linkedin-mcp.fastmcp.app/mcp/
```

---

## 🚨 Security

- This MCP exposes authenticated LinkedIn access. **Treat cookies like passwords.**
- Don't commit `.env` files. The `.gitignore` blocks them.
- For shared/public deployments, prefer per-request cookie headers (future enhancement) over server-wide env vars.
- Rotate cookies immediately if you suspect they leaked.

---

## 📊 Observability

FastMCP exposes basic stats at `/health` (when running in HTTP mode). For deeper observability:

- Log level: set `LOG_LEVEL=DEBUG` env var
- Metrics: FastMCP Cloud surfaces request counts + p95/p99 latency in its dashboard
- Tracing: add OpenTelemetry instrumentation if needed (not included by default)

---

## ❓ Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` | Cookies expired | Get fresh values from Chrome DevTools |
| `RuntimeError: Could not load LinkedIn auth` | No env vars + no local Chrome session | Set env vars OR log into LinkedIn in Chrome (macOS only for fallback) |
| `400 Bad Request` on posts endpoints | LinkedIn deprecated Voyager activity API | Use `fetch_my_posts_from_export_tool` with a data export ZIP instead |
| `Module not found` in Docker | Build missed a file | Check `Dockerfile` COPY directives; rebuild without cache |
| `pycookiecheat` errors on Linux/Windows | Chrome fallback is macOS-only | Use env-var auth instead |

---

## Next: the agent

Once deployed, point your LinkedIn-OS agent at the deployed URL. See `../linkedin-os/.mcp.json` for the config template.
