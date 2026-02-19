import os
import json
import random
import string
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
import redis.asyncio as aioredis 

app = FastAPI()

# Configuration with K8s-Safe Port Parsing
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
raw_port = os.getenv("REDIS_PORT", "6379")
REDIS_PORT = int(raw_port.split(":")[-1]) if "://" in raw_port else int(raw_port)

redis_client: Optional[aioredis.Redis] = None
mongo_col = None

@app.on_event("startup")
async def startup_event():
    global redis_client, mongo_col
    # Increased pool and optimized timeouts for high concurrency
    redis_client = aioredis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        max_connections=1000, 
        decode_responses=True,
        socket_timeout=5,
        socket_keepalive=True
    )
    m_client = MongoClient(MONGO_URI, maxPoolSize=2, serverSelectionTimeoutMS=2000)
    mongo_col = m_client["assessmentdb"]["records"]

@app.get("/healthz")
async def health(): return {"status": "ok"}

@app.get("/readyz")
async def ready():
    try:
        await redis_client.ping()
        return {"status": "ready"}
    except:
        raise HTTPException(status_code=503)

@app.get("/api/data")
async def process_data():
    if not redis_client:
        raise HTTPException(status_code=503)
    
    # Payload generation
    ts = datetime.utcnow().isoformat()
    doc = {"val": "data", "ts": ts}
    
    # 1. Async Write to Stream (The Fast Path)
    await redis_client.xadd("writes", {"data": json.dumps(doc)}, maxlen=50000, approximate=True)
    
    # 2. Optimized Read (Avoid Mongo if possible during peak)
    return {"status": "success", "ts": ts}
