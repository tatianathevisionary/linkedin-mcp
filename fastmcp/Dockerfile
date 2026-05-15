# LinkedIn MCP · Production Dockerfile
#
# Multi-stage build using uv for fast Python dependency resolution.
# Runs the FastMCP server in HTTP transport mode on port 8000.

FROM python:3.12-slim AS builder

# Install uv (fast Python package installer/resolver)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY pyproject.toml ./

# Install dependencies into a project-local virtualenv
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python --no-cache .

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the prepared virtualenv from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy source
COPY server.py auth.py voyager.py ./
COPY linkedin/ ./linkedin/

# Add venv to PATH so `python` and installed CLIs work
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose the FastMCP HTTP port
EXPOSE 8000

# Healthcheck — checks the MCP endpoint responds
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://127.0.0.1:8000/mcp/', timeout=3); exit(0 if r.status_code in (200, 404, 405) else 1)" || exit 1

# Run in HTTP mode for production
CMD ["python", "server.py", "--http"]
