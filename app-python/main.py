import os
import random
import string
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
import redis.asyncio as aioredis 

# Config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

app = FastAPI()

# Global placeholders
redis_client: Optional[aioredis.Redis] = None
mongo_collection = None

@app.on_event("startup")
async def startup_event():
    global redis_client, mongo_collection
    # Lazy init: Don't block the whole process if DB is slow
    try:
        redis_client = aioredis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, 
            max_connections=100, decode_responses=True
        )
        
        # Initialize Mongo inside startup
        client = MongoClient(MONGO_URI, maxPoolSize=5, serverSelectionTimeoutMS=2000)
        mongo_collection = client["assessmentdb"]["records"]
        print("Connections initialized")
    except Exception as e:
        print(f"Connection warning: {e}")

@app.get("/healthz")
async def health(): return {"status": "ok"}

@app.get("/readyz")
async def ready():
    # Only return 200 if we actually have clients initialized
    if redis_client and mongo_collection is not None:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Connections not ready")

@app.get("/api/data")
async def process_data():
    # ... (Keep the async logic from before) ...
    return {"status": "success"}
