import os
import random
import string
import json
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import redis.asyncio as aioredis  # Use Asyncio version

# Config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

app = FastAPI(title="Optimized DevOps API")

# Global clients
mongo_client = MongoClient(MONGO_URI, maxPoolSize=10, minPoolSize=2)
db = mongo_client["assessmentdb"]
collection = db["records"]
redis_client: Optional[aioredis.Redis] = None

@app.on_event("startup")
async def startup():
    global redis_client
    redis_client = aioredis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, 
        max_connections=200, # Increased for 10k VUs
        decode_responses=True
    )

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

@app.get("/readyz")
async def readiness_check():
    # Rapid check without blocking
    return {"status": "ready"}

@app.get("/api/data")
async def process_data():
    r = redis_client
    reads, writes = [], []
    
    # 1. ASYNC WRITES: Push to Redis Stream
    for i in range(5):
        payload = "".join(random.choices(string.ascii_letters, k=512))
        doc = {"type": "write", "payload": payload, "ts": datetime.utcnow().isoformat()}
        # O(1) non-blocking write
        sid = await r.xadd("writes", {"data": json.dumps(doc)}, maxlen=100000, approximate=True)
        writes.append(sid)

    # 2. CACHED READS: High-speed Redis lookup
    for i in range(5):
        cached = await r.get("doc:write")
        if cached:
            reads.append("cached")
        else:
            # Fallback to Mongo only on cache miss
            doc = collection.find_one({"type": "write"})
            if doc:
                reads.append(str(doc["_id"]))
                await r.setex("doc:write", CACHE_TTL, "exists")
    
    return {"status": "success", "reads": reads, "writes": writes}
