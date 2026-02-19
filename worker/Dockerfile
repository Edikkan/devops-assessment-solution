# ════════════════════════════════════════════════════════════════════════════
# Worker Consumer Dockerfile
# Purpose: Builds the worker that consumes from Redis Streams and writes to MongoDB
# ════════════════════════════════════════════════════════════════════════════

FROM python:3.11-slim

# Install redis-cli for health checks and netcat for init containers
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-tools \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Run as non-root user for security
RUN useradd -m -u 1000 worker && chown -R worker:worker /app
USER worker

# Start the worker
CMD ["python", "main.py"]
