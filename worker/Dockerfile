# ══════════════════════════════════════════════════════════════════════════════
# Worker Consumer - Async Write Processor
#
# Reads from Redis Stream and batches writes to MongoDB.
# ══════════════════════════════════════════════════════════════════════════════

FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r worker && useradd -r -g worker worker

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=worker:worker main.py .

USER worker

# Default environment variables
ENV MONGO_URI=mongodb://mongo:27017/assessmentdb
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV BATCH_SIZE=100
ENV FLUSH_INTERVAL=1.0

CMD ["python", "main.py"]
