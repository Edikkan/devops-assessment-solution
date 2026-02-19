import os
import time
import json
import signal
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from pymongo.errors import PyMongoError, BulkWriteError
import redis

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# TUNED FOR 10K VUs: 
# We want huge batches to minimize IOPS consumption.
# 50,000 writes/sec / 1000 per batch = 50 IOPS. Perfect.
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000")) 
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "2.0")) 
MAX_RETRIES = 5
RETRY_DELAY = 2.0

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
    try:
        # Use a small pool here; the API needs the connections more than the worker
        client = MongoClient(MONGO_URI, maxPoolSize=5, serverSelectionTimeoutMS=5000)
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
            # Clean up data before insert
            if "_id" in data: del data["_id"] 
            docs.append(data)
            message_ids.append(msg_id)
        except:
            message_ids.append(msg_id) # Ack bad JSON so it doesn't block
    
    if not docs:
        return len(message_ids)
    
    try:
        # 1 IOPS ticket used here regardless of batch size
        collection.insert_many(docs, ordered=False)
        return len(docs)
    except BulkWriteError as e:
        return e.details.get("nInserted", 0)
    except Exception as e:
        print(f"[worker] Critical Write Error: {e}")
        return 0

def main():
    mongo_client = connect_mongo()
    r = connect_redis()
    
    if not mongo_client or not r:
        sys.exit(1)

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
            # Pull a large chunk from the stream
            # Block for 2 seconds to allow the stream to fill up (batching at the source)
            response = r.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, 
                {WRITE_STREAM: ">"}, count=BATCH_SIZE, block=2000
            )
            
            if response:
                for _, stream_messages in response:
                    for msg_id, fields in stream_messages:
                        pending_messages.append((msg_id, fields))

            now = time.time()
            if pending_messages and (len(pending_messages) >= BATCH_SIZE or (now - last_flush) >= FLUSH_INTERVAL):
                # WRITE TO MONGO
                processed_count = process_batch(col, pending_messages)
                
                # ACKNOWLEDGE IN REDIS
                m_ids = [m[0] for m in pending_messages]
                r.xack(WRITE_STREAM, CONSUMER_GROUP, *m_ids)
                
                print(f"[worker] Flushed {len(pending_messages)} messages to Mongo.")
                
                pending_messages = []
                last_flush = now
                
                # IOPS PROTECTION:
                # Small sleep to ensure we don't exceed 100 IOPS if multiple workers are running
                time.sleep(0.05) 

        except Exception as e:
            print(f"[worker] Loop error: {e}")
            time.sleep(1)

    print("Worker stopped.")

if __name__ == "__main__":
    main()
