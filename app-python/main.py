import os
from fastapi import FastAPI, HTTPException
import redis.asyncio as aioredis 

app = FastAPI()

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
raw_port = os.getenv("REDIS_PORT", "6379")
REDIS_PORT = int(raw_port.split(":")[-1]) if "://" in raw_port else int(raw_port)

redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_client = aioredis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        max_connections=2000, 
        decode_responses=True
    )

@app.get("/healthz")
async def health(): return "ok"

@app.get("/readyz")
async def ready():
    try:
        await redis_client.ping()
        return "ready"
    except:
        raise HTTPException(status_code=503)

@app.get("/api/data")
async def process_data():
    try:
        await redis_client.xadd("writes", {"d": "1"}, maxlen=100000, approximate=True)
        return {"s": "ok"}
    except:
        raise HTTPException(status_code=503)
