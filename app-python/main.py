from fastapi import FastAPI
import aioredis
import motor.motor_asyncio
import os
import json
import time

app = FastAPI()

# Configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
STREAM_NAME = "write_stream"

# Global connection pools
redis = None
mongo_client = None

@app.on_event("startup")
async def startup():
    global redis, mongo_client
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)

@app.get("/api/data")
async def get_data():
    # 1. 5 Cache Reads (Simulating the requirement)
    # We use Redis to avoid hitting the 100 IOPS Mongo limit.
    for _ in range(5):
        cached = await redis.get("global_stats")

    # 2. 5 Stream Writes (Simulating the requirement)
    # Instead of blocking on Mongo, we push to a Redis Stream.
    payload = {"timestamp": time.time(), "action": "work"}
    for _ in range(5):
        await redis.xadd(STREAM_NAME, {"data": json.dumps(payload)})

    return {"status": "success", "source": "cache+stream"}
