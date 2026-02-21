from fastapi import FastAPI
from redis import asyncio as aioredis
import motor.motor_asyncio
import os
import json
import time

app = FastAPI()

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
STREAM_NAME = "write_stream"

redis = None
mongo_client = None

@app.on_event("startup")
async def startup():
    global redis, mongo_client
    # Initialize connection pools
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/api/data")
async def get_data():
    # 1. Simulate 5 Read Operations from Cache
    for _ in range(5):
        await redis.get("global_stats")

    # 2. Simulate 5 Write Operations via Stream
    payload = {"timestamp": time.time(), "action": "work"}
    for _ in range(5):
        await redis.xadd(STREAM_NAME, {"data": json.dumps(payload)})

    return {"status": "success", "source": "cache+stream"}
