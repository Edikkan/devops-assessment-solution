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

raw_redis_port = os.getenv("REDIS_PORT", "6379")
if "://" in raw_redis_port:
    REDIS_PORT = int(raw_redis_port.split(":")[-1])
else:
    REDIS_PORT = int(raw_redis_port)

redis_client: Optional[aioredis.Redis] = None
mongo_col = None

@app.on_event("startup")
async def startup_event():
    global redis_client, mongo_col
    redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, max_connections=200, decode_responses=True)
    # Lazy connect: don't let a slow Mongo kill the process
    m_client = MongoClient(MONGO_URI, maxPoolSize=2, serverSelectionTimeoutMS=2000)
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
    
    # Example Load Logic:
    doc = {"data": "assessment", "ts": datetime.utcnow().isoformat()}
    await redis_client.xadd("writes", {"data": json.dumps(doc)})
    return {"status": "success"}
