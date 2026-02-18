"""
DevOps Assessment API - Optimized Version

Key optimizations:
1. Redis caching for reads (reduces DB load)
2. Redis Streams for async writes (decouples write pressure)
3. Connection pooling for MongoDB and Redis
4. Efficient cache hit/miss handling
"""

import os
import time
import random
import string
import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import redis

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
APP_PORT = int(os.getenv("APP_PORT", "8000"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))  # Cache TTL in seconds

app = FastAPI(
    title="DevOps Assessment API (Optimized)",
    version="2.0.0",
)

# Connection pools
mongo_client: Optional[MongoClient] = None
db = None
collection = None
redis_client: Optional[redis.Redis] = None

# Redis stream configuration
WRITE_STREAM = "writes"
WRITE_STREAM_MAX_LEN = 100000  # Max stream length to prevent unbounded growth


def get_mongo_client() -> Optional[MongoClient]:
    """Get or create MongoDB client with connection pooling."""
    global mongo_client
    if mongo_client is None:
        try:
            mongo_client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                maxPoolSize=50,  # Connection pooling
                minPoolSize=10,
                maxIdleTimeMS=30000,
            )
            # Verify connection
            mongo_client.admin.command("ping")
        except PyMongoError as e:
            print(f"[mongo] connection failed: {e}")
            return None
    return mongo_client


def get_collection():
    """Get MongoDB collection."""
    global db, collection
    if collection is None:
        client = get_mongo_client()
        if client:
            db = client["assessmentdb"]
            collection = db["records"]
    return collection


def get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client with connection pooling."""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30,
                max_connections=50,  # Connection pooling
            )
            # Verify connection
            redis_client.ping()
        except redis.ConnectionError as e:
            print(f"[redis] connection failed: {e}")
            return None
    return redis_client


def random_payload(size: int = 512) -> str:
    """Generate random payload string."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=size))


def generate_cache_key(doc_type: str = "write") -> str:
    """Generate cache key for reads."""
    return f"doc:{doc_type}"


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup."""
    # Connect to MongoDB
    for attempt in range(1, 11):
        if get_collection() is not None:
            print(f"[mongo] connected on attempt {attempt}")
            break
        print(f"[mongo] attempt {attempt}/10 failed, retrying in 2s...")
        time.sleep(2)
    else:
        print("[mongo] could not connect on startup")
    
    # Connect to Redis
    for attempt in range(1, 11):
        if get_redis_client() is not None:
            print(f"[redis] connected on attempt {attempt}")
            break
        print(f"[redis] attempt {attempt}/10 failed, retrying in 2s...")
        time.sleep(2)
    else:
        print("[redis] could not connect on startup")


# ── Health & Readiness Endpoints ─────────────────────────────────────────────

@app.get("/healthz")
def health_check():
    """Liveness probe - always returns 200."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/readyz")
def readiness_check():
    """Readiness probe - checks MongoDB and Redis connectivity."""
    mongo_ok = get_collection() is not None
    redis_ok = get_redis_client() is not None
    
    if mongo_ok and redis_ok:
        return {
            "status": "ready",
            "mongo": "connected",
            "redis": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    status_code = 503
    detail = {
        "status": "not ready",
        "mongo": "connected" if mongo_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
    }
    raise HTTPException(status_code=status_code, detail=detail)


# ── Core API Endpoint (Optimized) ────────────────────────────────────────────

@app.get("/api/data")
def process_data():
    """
    Optimized /api/data endpoint.
    
    Writes: Published to Redis Stream (async, acknowledged immediately)
    Reads: Served from Redis cache when possible, fallback to MongoDB
    """
    col = get_collection()
    r = get_redis_client()
    
    if col is None:
        raise HTTPException(status_code=503, detail="MongoDB not reachable")
    if r is None:
        raise HTTPException(status_code=503, detail="Redis not reachable")
    
    reads: List[Optional[str]] = []
    writes: List[str] = []
    
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # WRITES: Publish to Redis Stream (async, non-blocking)
        # The worker consumer will batch these to MongoDB
        # ═══════════════════════════════════════════════════════════════════════
        for i in range(5):
            doc = {
                "type": "write",
                "index": i,
                "payload": random_payload(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Add to Redis Stream - O(1) operation, ~sub-millisecond latency
            stream_id = r.xadd(
                WRITE_STREAM,
                {"data": json.dumps(doc)},
                maxlen=WRITE_STREAM_MAX_LEN,
                approximate=True,
            )
            writes.append(stream_id)
            
            # Also update cache with this new document (write-through cache)
            cache_key = f"doc:write:{stream_id}"
            r.setex(cache_key, CACHE_TTL, json.dumps(doc))
        
        # ═══════════════════════════════════════════════════════════════════════
        # READS: Try cache first, fallback to MongoDB
        # Redis: ~100K+ ops/sec | MongoDB: ~100 ops/sec
        # ═══════════════════════════════════════════════════════════════════════
        for i in range(5):
            # Strategy: Try to get from cache first
            cache_key = generate_cache_key("write")
            cached_doc = r.get(cache_key)
            
            if cached_doc:
                # Cache hit - serve from Redis (sub-millisecond)
                doc_data = json.loads(cached_doc)
                # Generate a consistent ID from the cache key for demonstration
                reads.append(doc_data.get("_id", f"cached-{i}"))
            else:
                # Cache miss - fallback to MongoDB
                try:
                    doc = col.find_one({"type": "write"})
                    if doc:
                        doc_id = str(doc["_id"])
                        reads.append(doc_id)
                        
                        # Populate cache for future reads (with TTL)
                        r.setex(cache_key, CACHE_TTL, json.dumps({
                            "_id": doc_id,
                            "type": doc.get("type"),
                            "timestamp": doc.get("timestamp", datetime.utcnow().isoformat()),
                        }))
                    else:
                        reads.append(None)
                except PyMongoError:
                    reads.append(None)
        
        return JSONResponse(content={
            "status": "success",
            "reads": reads,
            "writes": writes,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    except redis.RedisError as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")


# ── Stats Endpoint ───────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    """Collection document count and stream stats."""
    col = get_collection()
    r = get_redis_client()
    
    if col is None:
        raise HTTPException(status_code=503, detail="MongoDB not reachable")
    
    try:
        doc_count = col.count_documents({})
        
        # Get Redis stream info
        stream_len = 0
        if r:
            try:
                stream_len = r.xlen(WRITE_STREAM)
            except redis.RedisError:
                pass
        
        return {
            "total_documents": doc_count,
            "pending_writes_in_stream": stream_len,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Cache Management Endpoints (Optional - for debugging) ────────────────────

@app.get("/api/cache/stats")
def get_cache_stats():
    """Get Redis cache statistics."""
    r = get_redis_client()
    if r is None:
        raise HTTPException(status_code=503, detail="Redis not reachable")
    
    try:
        info = r.info()
        return {
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except redis.RedisError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cache/clear")
def clear_cache():
    """Clear all cached data (for testing)."""
    r = get_redis_client()
    if r is None:
        raise HTTPException(status_code=503, detail="Redis not reachable")
    
    try:
        # Only clear doc:* keys, not the stream
        keys = r.keys("doc:*")
        if keys:
            r.delete(*keys)
        return {"status": "cleared", "keys_removed": len(keys)}
    except redis.RedisError as e:
        raise HTTPException(status_code=500, detail=str(e))
