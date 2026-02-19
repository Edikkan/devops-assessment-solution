import os
import random
import string
import json
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
import redis.asyncio as aioredis 

app = FastAPI()

# --- K8s-Safe Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

# FIX: Extracts '6379' from K8s injected 'tcp://10.43...:6379'
raw_redis_port = os.getenv("REDIS_PORT", "6379")
REDIS_PORT = int(raw_redis_port.split(":")[-1]) if "://" in raw_redis_port else int(raw_redis_port)

redis_client: Optional[aioredis.Redis] = None
mongo_col = None

@app.on_event("startup")
async def startup_event():
    global redis_client, mongo_col
    # Increased pool size to handle the 10k VU pressure
    redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, max_connections=500, decode_responses=True)
    m_client = MongoClient(MONGO_URI, maxPoolSize=4, serverSelectionTimeoutMS=5000)
    mongo_col = m_client["assessmentdb"]["records"]

@app.get("/healthz")
async def health(): return {"status": "ok"}

@app.get("/readyz")
async def ready():
    try:
        if redis_client:
            await redis_client.ping()
            return {"status": "ready"}
    except:
        pass
    raise HTTPException(status_code=503)

@app.get("/api/data")
async def process_data():
    if not redis_client or mongo_col is None:
        raise HTTPException(status_code=503)
    
    # High-speed ingestion via Redis Streams
    doc = {"data": "assessment", "ts": datetime.utcnow().isoformat()}
    await redis_client.xadd("writes", {"data": json.dumps(doc)}, maxlen=100000, approximate=True)
    return {"status": "success"}
