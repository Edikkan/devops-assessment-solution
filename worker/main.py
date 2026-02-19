import os
import time
import json
import signal
import sys
import random # Added for jitter
from datetime import datetime
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from pymongo.errors import PyMongoError, BulkWriteError
import redis

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

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
    # JITTER: Prevents "Thundering Herd" during rollout
    time.sleep(random.uniform(1, 5))
    try:
        # maxPoolSize=2 is plenty for a worker that only does batch inserts
        client = MongoClient(MONGO_URI, maxPoolSize=2, serverSelectionTimeoutMS=10000)
        client.admin.command("ping")
        return client
    except Exception as e:
        print(f"[mongo] connection failed: {e}")
        return None

def connect_redis():
    try:
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    except Exception as e:
        print(f"[redis] connection failed: {e}")
        return None

def process_batch(collection, messages: List[tuple]) -> int:
    if not messages:
        return 0
    
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
    
    if not docs:
        return len(message_ids)
    
    try:
        # Use bulk_write or insert_many. insert_many is fine here.
        collection.insert_many(docs, ordered=False)
        return len(docs)
    except BulkWriteError as e:
        return e.details.get("nInserted", 0)
    except Exception as e:
        print(f"[worker] Critical Write Error: {e}")
        return 0

def main():
    # Retry loop to ensure it doesn't just die if Mongo is slow
    mongo_client = None
    while running and not mongo_client:
        mongo_client = connect_mongo()
        if not mongo_client: time.sleep(5)

    r = None
    while running and not r:
        r = connect_redis()
        if not r: time.sleep(5)

    if not running: return

    # Ensure group exists
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
            # We use a 2s block to aggregate data in memory rather than hitting Mongo
            response = r.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, 
                {WRITE_STREAM: ">"}, count=BATCH_SIZE, block=2000
            )
            
            if response:
                for _, stream_messages in response:
                    for msg_id, fields in stream_messages:
                        pending_messages.append((msg_id, fields))

            now = time.time()
            # Flush logic: either batch is full or time is up
            if pending_messages and (len(pending_messages) >= BATCH_SIZE or (now - last_flush) >= FLUSH_INTERVAL):
                processed_count = process_batch(col, pending_messages)
                
                m_ids = [m[0] for m in pending_messages]
                # Pipeline the ACKs in the future if Redis becomes the bottleneck
                r.xack(WRITE_STREAM, CONSUMER_GROUP, *m_ids)
                
                print(f"[worker] Flushed {len(pending_messages)} messages to Mongo.")
                
                pending_messages = []
                last_flush = now
                
                # Mandatory backoff to stay under IOPS limit
                time.sleep(0.1) 

        except Exception as e:
            print(f"[worker] Loop error: {e}")
            time.sleep(2)

    print("Worker stopped.")

if __name__ == "__main__":
    main()
