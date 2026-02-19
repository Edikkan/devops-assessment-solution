import os
import time
import json
import signal
import sys
import random
from datetime import datetime
from typing import List, Dict, Any, Optional
from pymongo import MongoClient
from pymongo.errors import PyMongoError, BulkWriteError
import redis

# --- K8s-Safe Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

# FIX: Strip 'tcp://' prefix injected by Kubernetes Service discovery
raw_redis_port = os.getenv("REDIS_PORT", "6379")
if "://" in raw_redis_port:
    REDIS_PORT = int(raw_redis_port.split(":")[-1])
else:
    REDIS_PORT = int(raw_redis_port)

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000")) 
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "2.0")) 
WRITE_STREAM = "writes"
CONSUMER_GROUP = "mongo-writers"
CONSUMER_NAME = os.getenv("HOSTNAME", "worker-1")

running = True

def signal_handler(signum, frame):
    global running
    print(f"[worker] shutting down...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def connect_mongo():
    time.sleep(random.uniform(1, 3)) # Jitter to let API pods connect first
    try:
        client = MongoClient(MONGO_URI, maxPoolSize=2, serverSelectionTimeoutMS=10000)
        client.admin.command("ping")
        return client
    except Exception as e:
        print(f"[mongo] connection failed: {e}")
        return None

def connect_redis():
    try:
        # Note: worker uses synchronous redis client
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    except Exception as e:
        print(f"[redis] connection failed: {e}")
        return None

def process_batch(collection, messages: List[tuple]) -> int:
    if not messages: return 0
    docs = []
    message_ids = []
    for msg_id, fields in messages:
        try:
            data = json.loads(fields.get("data", "{}"))
            if "_id" in data: del data["_id"] 
            docs.append(data)
            message_ids.append(msg_id)
        except:
            message_ids.append(msg_id)
    
    if not docs: return len(message_ids)
    try:
        collection.insert_many(docs, ordered=False)
        return len(docs)
    except BulkWriteError as e:
        return e.details.get("nInserted", 0)
    except Exception as e:
        print(f"[worker] Critical Write Error: {e}")
        return 0

def main():
    mongo_client = None
    while running and not mongo_client:
        mongo_client = connect_mongo()
        if not mongo_client: time.sleep(2)

    r = None
    while running and not r:
        r = connect_redis()
        if not r: time.sleep(2)

    if not running: return

    try:
        r.xgroup_create(WRITE_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    except:
        pass
    
    db = mongo_client["assessmentdb"]
    col = db["records"]
    pending_messages = []
    last_flush = time.time()

    print(f"Worker started. Batch: {BATCH_SIZE}, Interval: {FLUSH_INTERVAL}s")

    while running:
        try:
            response = r.xreadgroup(CONSUMER_GROUP, CONSUMER_NAME, {WRITE_STREAM: ">"}, count=BATCH_SIZE, block=2000)
            if response:
                for _, stream_messages in response:
                    for msg_id, fields in stream_messages:
                        pending_messages.append((msg_id, fields))

            now = time.time()
            if pending_messages and (len(pending_messages) >= BATCH_SIZE or (now - last_flush) >= FLUSH_INTERVAL):
                process_batch(col, pending_messages)
                m_ids = [m[0] for m in pending_messages]
                r.xack(WRITE_STREAM, CONSUMER_GROUP, *m_ids)
                pending_messages = []
                last_flush = now
                time.sleep(0.1) 
        except Exception as e:
            print(f"[worker] Loop error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
