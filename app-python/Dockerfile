# ══════════════════════════════════════════════════════════════════════════════
# DevOps Assessment — Python / FastAPI (OPTIMIZED)
#
# Optimizations applied:
#   - Multi-stage build (smaller final image)
#   - Non-root user (security best practice)
#   - Multiple uvicorn workers (saturate CPU)
#   - .dockerignore awareness
# ══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Production ───────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

EXPOSE 8000

# Multiple workers to saturate CPU cores
# Workers = 2-4 × CPU cores (assuming 2 cores, use 4 workers)
# Keep-alive and timeout tuned for high concurrency
CMD ["uvicorn", "main:app", 
     "--host", "0.0.0.0", 
     "--port", "8000", 
     "--workers", "4",
     "--loop", "uvloop",
     "--http", "httptools",
     "--keep-alive", "5",
     "--timeout-keep-alive", "30"]
