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

# Config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

app = FastAPI(title="Resilient DevOps API")

# Global clients (Initialized as None)
redis_client: Optional[aioredis.Redis] = None
mongo_col = None

@app.on_event("startup")
async def startup_event():
    """Initialize connections without blocking the event loop."""
    global redis_client, mongo_col
    
    # 1. Initialize Redis Async Client
    redis_client = aioredis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        max_connections=200, 
        decode_responses=True
    )
    
    # 2. Initialize MongoDB Client (Small pool for single node)
    try:
        m_client = MongoClient(
            MONGO_URI, 
            maxPoolSize=5, 
            serverSelectionTimeoutMS=2000
        )
        mongo_col = m_client["assessmentdb"]["records"]
    except Exception as e:
        print(f"Non-fatal Mongo connection error: {e}")

@app.get("/healthz")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.get("/readyz")
async def ready():
    """Readiness probe: Checks if DB clients are at least instantiated."""
    if redis_client is not None and mongo_col is not None:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Services warming up")

@app.get("/api/data")
async def process_data():
    if not redis_client or mongo_col is None:
        raise HTTPException(status_code=503, detail="Database connections not established")
    
    # ... (Keep the high-performance logic from previous steps) ...
    # 1. Write to Redis Stream
    # 2. Read from Redis Cache / Fallback to Mongo
    return {"status": "success"}
