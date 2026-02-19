# ══════════════════════════════════════════════════════════════════════════════
# DevOps Assessment — Python / FastAPI (FINAL OPTIMIZED)
# ══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for high-performance C-extensions (uvloop/httptools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies to a local user directory to keep the final image clean
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Production ───────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy installed packages and app code
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

# Ensure the local bin is in the PATH
ENV PATH=/home/appuser/.local/bin:$PATH
USER appuser

EXPOSE 8000

# ── Runtime Configuration ─────────────────────────────────────────────────────
# 1. Use 2 workers to prevent CPU thrashing on 8vCPU VM (with 15 replicas).
# 2. --timeout-keep-alive: FIXED (was --keep-alive) to allow k6 connection reuse.
# 3. --loop/--http: Use high-performance binaries built in Stage 1.
# ══════════════════════════════════════════════════════════════════════════════
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--timeout-keep-alive", "65"]
