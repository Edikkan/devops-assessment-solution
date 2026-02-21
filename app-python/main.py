from fastapi import FastAPI
from redis import asyncio as aioredis
import motor.motor_asyncio
import os, json, time

app = FastAPI()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
STREAM_NAME = "write_stream"
redis = None

@app.on_event("startup")
async def startup():
    global redis
    # High-performance pool for 10k concurrent VUs
    redis = await aioredis.from_url(
        REDIS_URL, 
        decode_responses=True,
        max_connections=5000 
    )

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/api/data")
async def get_data():
    # Pipeline reduces 10 network roundtrips to 2
    async with redis.pipeline(transaction=False) as pipe:
        for _ in range(5):
            pipe.get("global_stats")
        
        payload = {"data": json.dumps({"ts": time.time()})}
        for _ in range(5):
            pipe.xadd(STREAM_NAME, payload)
        
        await pipe.execute()
        
    return {"status": "success"}
