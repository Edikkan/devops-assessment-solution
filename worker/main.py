import os
import time
import json
import signal
import sys
import random
from pymongo import MongoClient
import redis

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
raw_port = os.getenv("REDIS_PORT", "6379")
REDIS_PORT = int(raw_port.split(":")[-1]) if "://" in raw_port else int(raw_port)

BATCH_SIZE = 1000
FLUSH_INTERVAL = 2.0
WRITE_STREAM = "writes"
CONSUMER_GROUP = "mongo-writers"
CONSUMER_NAME = os.getenv("HOSTNAME", "worker-1")

running = True
def signal_handler(sig, frame): global running; running = False
signal.signal(signal.SIGTERM, signal_handler)

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    m_client = MongoClient(MONGO_URI, maxPoolSize=2)
    col = m_client["assessmentdb"]["records"]

    try:
        r.xgroup_create(WRITE_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    except: pass

    pending = []
    last_flush = time.time()

    while running:
        try:
            # High-speed batch consumption
            resp = r.xreadgroup(CONSUMER_GROUP, CONSUMER_NAME, {WRITE_STREAM: ">"}, count=BATCH_SIZE, block=1000)
            if resp:
                for _, messages in resp:
                    for msg_id, fields in messages:
                        data = json.loads(fields.get("data", "{}"))
                        if "_id" in data: del data["_id"]
                        pending.append((msg_id, data))

            if pending and (len(pending) >= BATCH_SIZE or (time.time() - last_flush) > FLUSH_INTERVAL):
                col.insert_many([p[1] for p in pending], ordered=False)
                r.xack(WRITE_STREAM, CONSUMER_GROUP, *[p[0] for p in pending])
                pending = []
                last_flush = time.time()
                time.sleep(0.05) # IOPS protection
        except Exception as e:
            time.sleep(1)

if __name__ == "__main__":
    main()
