import os
import random
import string
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
import redis.asyncio as aioredis 

app = FastAPI()

# Config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

redis_client: Optional[aioredis.Redis] = None
mongo_col = None

@app.on_event("startup")
async def startup_event():
    global redis_client, mongo_col
    redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, max_connections=100, decode_responses=True)
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
    # WRITES: Async Stream
    for i in range(5):
        doc = {"payload": "".join(random.choices(string.ascii_letters, k=512)), "ts": datetime.utcnow().isoformat()}
        await redis_client.xadd("writes", {"data": json.dumps(doc)}, maxlen=100000, approximate=True)
    
    # READS: Cache-Aside
    reads = []
    for i in range(5):
        cached = await redis_client.get("doc:latest")
        if cached:
            reads.append("hit")
        else:
            # Fallback to Mongo (constrained path)
            res = mongo_col.find_one({"type": "write"})
            reads.append(str(res["_id"]) if res else "miss")
            await redis_client.setex("doc:latest", 60, "1")
            
    return {"status": "success", "reads": reads}
