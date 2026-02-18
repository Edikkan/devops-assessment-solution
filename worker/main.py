"""
Worker Consumer - Async Write Processor

Purpose:
    Reads write operations from Redis Stream and batches them to MongoDB.
    This decouples the write pressure from the API, allowing the system
    to handle 10K concurrent users against a 100 IOPS MongoDB.

Design:
    - Batches writes for efficiency
    - Throttles to respect MongoDB IOPS limits
    - Acknowledges processed messages in Redis Stream
    - Handles failures gracefully with retry logic
"""

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

# Tuning parameters
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))  # Writes per batch
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "1.0"))  # Seconds between flushes
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "1.0"))

# Redis stream configuration
WRITE_STREAM = "writes"
CONSUMER_GROUP = "mongo-writers"
CONSUMER_NAME = os.getenv("HOSTNAME", "worker-1")

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    print(f"[worker] received signal {signum}, shutting down gracefully...")
    running = False


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def connect_mongo() -> Optional[MongoClient]:
    """Connect to MongoDB with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                maxPoolSize=10,
                minPoolSize=5,
            )
            client.admin.command("ping")
            print("[mongo] connected successfully")
            return client
        except PyMongoError as e:
            print(f"[mongo] connection attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return None


def connect_redis() -> Optional[redis.Redis]:
    """Connect to Redis with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            r.ping()
            print("[redis] connected successfully")
            return r
        except redis.ConnectionError as e:
            print(f"[redis] connection attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return None


def ensure_consumer_group(r: redis.Redis) -> bool:
    """Create consumer group if it doesn't exist."""
    try:
        r.xgroup_create(WRITE_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        print(f"[redis] created consumer group: {CONSUMER_GROUP}")
        return True
    except redis.ResponseError as e:
        if "already exists" in str(e):
            return True
        print(f"[redis] error creating consumer group: {e}")
        return False


def process_batch(collection, messages: List[Dict]) -> int:
    """
    Process a batch of messages by inserting into MongoDB.
    
    Returns:
        Number of successfully processed messages
    """
    if not messages:
        return 0
    
    docs = []
    message_ids = []
    
    for msg_id, fields in messages:
        try:
            data = json.loads(fields.get("data", "{}"))
            # Convert timestamp string back to datetime if needed
            if "timestamp" in data and isinstance(data["timestamp"], str):
                # Keep as string for simplicity
                pass
            docs.append(data)
            message_ids.append(msg_id)
        except json.JSONDecodeError as e:
            print(f"[worker] failed to parse message {msg_id}: {e}")
            # Still acknowledge to avoid reprocessing bad messages
            message_ids.append(msg_id)
    
    if not docs:
        return len(message_ids)
    
    # Insert batch into MongoDB
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = collection.insert_many(docs, ordered=False)
            processed = len(result.inserted_ids)
            print(f"[worker] inserted batch of {processed} documents")
            return processed
        except BulkWriteError as e:
            # Some writes may have succeeded
            write_errors = e.details.get("writeErrors", [])
            processed = len(docs) - len(write_errors)
            print(f"[worker] partial batch success: {processed}/{len(docs)} (errors: {len(write_errors)})")
            return processed
        except PyMongoError as e:
            print(f"[worker] batch insert attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                print(f"[worker] failed to insert batch after {MAX_RETRIES} attempts")
                return 0
    
    return 0


def acknowledge_messages(r: redis.Redis, message_ids: List[str]) -> bool:
    """Acknowledge processed messages in Redis Stream."""
    if not message_ids:
        return True
    
    try:
        # Use XACK to acknowledge messages
        ack_count = r.xack(WRITE_STREAM, CONSUMER_GROUP, *message_ids)
        if ack_count != len(message_ids):
            print(f"[worker] acknowledged {ack_count}/{len(message_ids)} messages")
        return True
    except redis.RedisError as e:
        print(f"[worker] failed to acknowledge messages: {e}")
        return False


def claim_stale_messages(r: redis.Redis) -> List:
    """Claim messages from dead/idle consumers."""
    try:
        # Claim messages idle for more than 30 seconds
        pending = r.xpending_range(
            WRITE_STREAM,
            CONSUMER_GROUP,
            min="-",
            max="+",
            count=100,
        )
        
        stale_ids = []
        for item in pending:
            if item.get("time_since_delivered", 0) > 30000:  # 30 seconds
                stale_ids.append(item["message_id"])
        
        if stale_ids:
            claimed = r.xclaim(
                WRITE_STREAM,
                CONSUMER_GROUP,
                CONSUMER_NAME,
                min_idle_time=30000,
                message_ids=stale_ids,
            )
            if claimed:
                print(f"[worker] claimed {len(claimed)} stale messages")
                return claimed
        
        return []
    except redis.RedisError as e:
        print(f"[worker] error claiming stale messages: {e}")
        return []


def main():
    """Main worker loop."""
    print("═" * 60)
    print("  Worker Consumer - Async Write Processor")
    print("═" * 60)
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Flush interval: {FLUSH_INTERVAL}s")
    print(f"  Consumer: {CONSUMER_NAME}")
    print("═" * 60)
    
    # Connect to databases
    mongo_client = connect_mongo()
    if not mongo_client:
        print("[worker] failed to connect to MongoDB, exiting")
        sys.exit(1)
    
    r = connect_redis()
    if not r:
        print("[worker] failed to connect to Redis, exiting")
        sys.exit(1)
    
    # Ensure consumer group exists
    if not ensure_consumer_group(r):
        print("[worker] failed to create consumer group, exiting")
        sys.exit(1)
    
    db = mongo_client["assessmentdb"]
    collection = db["records"]
    
    # Statistics
    total_processed = 0
    last_flush_time = time.time()
    pending_messages = []
    
    print("[worker] starting main loop...")
    
    while running:
        try:
            # Read messages from stream (non-blocking)
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={WRITE_STREAM: ">"},  ">" means undelivered messages
                count=BATCH_SIZE,
                block=1000,  # Block for 1 second
            )
            
            if messages:
                # Extract message data
                for stream_name, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        pending_messages.append((msg_id, fields))
            
            # Also check for stale messages periodically
            if len(pending_messages) < BATCH_SIZE // 2:
                stale = claim_stale_messages(r)
                for msg_id, fields in stale:
                    pending_messages.append((msg_id, fields))
            
            # Check if we should flush the batch
            current_time = time.time()
            should_flush = (
                len(pending_messages) >= BATCH_SIZE or
                (pending_messages and current_time - last_flush_time >= FLUSH_INTERVAL)
            )
            
            if should_flush and pending_messages:
                # Process the batch
                processed = process_batch(collection, pending_messages)
                total_processed += processed
                
                # Acknowledge all messages (even failed ones to avoid reprocessing)
                message_ids = [msg_id for msg_id, _ in pending_messages]
                acknowledge_messages(r, message_ids)
                
                if processed > 0:
                    print(f"[worker] total processed: {total_processed}")
                
                # Clear pending messages
                pending_messages = []
                last_flush_time = current_time
            
            # Small sleep to prevent tight loop when idle
            if not messages:
                time.sleep(0.1)
        
        except redis.RedisError as e:
            print(f"[worker] Redis error: {e}")
            time.sleep(RETRY_DELAY)
        
        except PyMongoError as e:
            print(f"[worker] MongoDB error: {e}")
            time.sleep(RETRY_DELAY)
        
        except Exception as e:
            print(f"[worker] unexpected error: {e}")
            time.sleep(RETRY_DELAY)
    
    # Flush any remaining messages before shutdown
    if pending_messages:
        print(f"[worker] flushing {len(pending_messages)} remaining messages...")
        process_batch(collection, pending_messages)
        message_ids = [msg_id for msg_id, _ in pending_messages]
        acknowledge_messages(r, message_ids)
    
    print(f"[worker] shutdown complete. Total processed: {total_processed}")


if __name__ == "__main__":
    main()
