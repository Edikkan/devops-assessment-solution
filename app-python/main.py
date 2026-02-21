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
    # Connection pooling is the secret to 10k concurrency
    redis = await aioredis.from_url(
        REDIS_URL, 
        decode_responses=True,
        max_connections=2000  # Large pool to handle the socket surge
    )
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
        MONGO_URL,
        maxPoolSize=100,      # Constrain Mongo to stay under IOPS limit
        minPoolSize=20
    )

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/api/data")
async def get_data():
    # Caching and Streaming to decouple from Mongo
    for _ in range(5):
        await redis.get("global_stats")

    payload = {"timestamp": time.time(), "action": "work"}
    for _ in range(5):
        await redis.xadd(STREAM_NAME, {"data": json.dumps(payload)})

    return {"status": "success", "source": "cache+stream"}
