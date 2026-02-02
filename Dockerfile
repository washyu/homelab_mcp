# Homelab MCP Server - HTTP Mode
# Multi-stage build for smaller image size

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Create virtual environment and install dependencies
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install .

# --- Production stage ---
FROM python:3.12-slim

# Install runtime dependencies (SSH client for remote operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash mcp

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY run_server.py ./
COPY certs/ ./certs/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # MCP HTTP configuration
    MCP_HTTP_ENABLED=true \
    MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8080 \
    MCP_AUTH_ENABLED=true \
    # SSL configuration (set these to enable HTTPS)
    MCP_SSL_CERT="" \
    MCP_SSL_KEY=""

# Create directories for data persistence
RUN mkdir -p /home/mcp/.homelab_mcp /home/mcp/.ssh && \
    chown -R mcp:mcp /home/mcp /app

# Switch to non-root user
USER mcp

# Health check (uses -k to allow self-signed certs)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -sfk http://localhost:8080/health || curl -sfk https://localhost:8080/health || exit 1

# Expose HTTP port
EXPOSE 8080

# Run the server in HTTP mode
CMD ["python", "run_server.py", "--http"]
