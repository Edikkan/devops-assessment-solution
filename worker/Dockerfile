FROM python:3.11-slim

# Stay with netcat for your initContainers
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-tools \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

# Add a simple health check script that doesn't need to load the whole Python VM
RUN echo 'import redis; r = redis.Redis(host="redis"); r.ping()' > health.py

RUN useradd -m -u 1000 worker && chown -R worker:worker /app
USER worker

CMD ["python", "main.py"]
