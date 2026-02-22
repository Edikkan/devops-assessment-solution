from fastapi import FastAPI
from redis import asyncio as aioredis
import motor.motor_asyncio
import os, json, time

app = FastAPI()

# Use internal K8s DNS for Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis.assessment.svc.cluster.local:6379")
STREAM_NAME = "write_stream"
redis = None

@app.on_event("startup")
async def startup():
    global redis
    # 5000 connections provides enough headroom for 10k VUs with 1s sleep
    redis = await aioredis.from_url(
        REDIS_URL, 
        decode_responses=True,
        max_connections=5000,
        socket_timeout=5,
        retry_on_timeout=True
    )

@app.get("/healthz")
async def healthz():
    try:
        await redis.ping()
        return {"status": "ok"}
    except Exception:
        return {"status": "error"}, 500

@app.get("/api/data")
async def get_data():
    async with redis.pipeline(transaction=False) as pipe:
        # Fulfilling the requirement: 5 reads + 5 writes
        for _ in range(5):
            pipe.get("global_stats")
        
        payload = {"data": json.dumps({"ts": time.time()})}
        for _ in range(5):
            pipe.xadd(STREAM_NAME, payload)
        
        await pipe.execute()
        
    return {"status": "success"}
