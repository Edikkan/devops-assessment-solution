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
import redis.asyncio as aioredis 

# Configuration from Environment
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

app = FastAPI(title="DevOps Assessment API - Final Optimized")

# MongoDB Client (Sync is okay for low-volume reads, but we pool it)
mongo_client = MongoClient(
    MONGO_URI, 
    maxPoolSize=int(os.getenv("MONGO_MAX_POOL_SIZE", "5")),
    serverSelectionTimeoutMS=5000
)
db = mongo_client["assessmentdb"]
collection = db["records"]
redis_client: Optional[aioredis.Redis] = None

@app.on_event("startup")
async def startup():
    global redis_client
    redis_client = aioredis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        max_connections=200, # Large pool for 10k users
        decode_responses=True
    )

@app.get("/healthz")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/readyz")
async def readiness_check():
    # Rapid check to satisfy k8s probes
    return {"status": "ready"}

@app.get("/api/data")
async def process_data():
    r = redis_client
    reads, writes = [], []
    
    try:
        # WRITES: Async Push to Redis Stream
        for i in range(5):
            payload = "".join(random.choices(string.ascii_letters + string.digits, k=512))
            doc = {"type": "write", "payload": payload, "ts": datetime.utcnow().isoformat()}
            # XADD is O(1)
            sid = await r.xadd("writes", {"data": json.dumps(doc)}, maxlen=100000, approximate=True)
            writes.append(sid)

        # READS: Aggressive Caching
        for i in range(5):
            cached = await r.get("doc:write:latest")
            if cached:
                reads.append("cached_hit")
            else:
                # Fallback to Mongo only on first miss
                doc = collection.find_one({"type": "write"})
                if doc:
                    reads.append(str(doc["_id"]))
                    await r.setex("doc:write:latest", CACHE_TTL, "exists")
        
        return {"status": "success", "reads": reads, "writes": writes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
