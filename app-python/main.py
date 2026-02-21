from fastapi import FastAPI
from redis import asyncio as aioredis
import os, json, time

app = FastAPI()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis.assessment.svc.cluster.local:6379")
STREAM_NAME = "write_stream"
redis = None

@app.on_event("startup")
async def startup():
    global redis
    # Using a massive pool size and aggressive timeouts to prevent blocking
    redis = await aioredis.from_url(
        REDIS_URL, 
        decode_responses=True,
        max_connections=10000, 
        socket_connect_timeout=1,
        socket_keepalive=True
    )

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/api/data")
async def get_data():
    # Batching the 5 reads and 5 writes into 2 network trips
    async with redis.pipeline(transaction=False) as pipe:
        for _ in range(5):
            pipe.get("global_stats")
        payload = {"data": json.dumps({"ts": time.time()})}
        for _ in range(5):
            pipe.xadd(STREAM_NAME, payload)
        await pipe.execute()
    return {"status": "success"}
