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
m_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client, mongo_col, m_client
    
    # Initialize Redis Async Client
    redis_client = aioredis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        max_connections=100, # Lowered to reduce memory footprint
        decode_responses=True
    )
    
    # Initialize MongoDB Client with EXTREMELY conservative pooling
    try:
        # We do NOT ping here. We just create the object.
        m_client = MongoClient(
            MONGO_URI, 
            maxPoolSize=2, # Use only 2 connections per pod to save Mongo RAM
            minPoolSize=1,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000
        )
        mongo_col = m_client["assessmentdb"]["records"]
    except Exception as e:
        print(f"Deferred Mongo initialization: {e}")

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.get("/readyz")
async def ready():
    """Readiness probe: Validates connections without crashing the process."""
    try:
        # Check Redis
        if redis_client:
            await redis_client.ping()
        
        # Check Mongo
        if m_client:
            m_client.admin.command('ping')
            
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Downstream services busy")

@app.get("/api/data")
async def process_data():
    if not redis_client or mongo_col is None:
        raise HTTPException(status_code=503, detail="Database connections not established")
    
    # ... logic for Redis Stream writes and cached reads ...
    return {"status": "success"}
