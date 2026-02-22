import time
import json
import redis
import pymongo

# Connections
r = redis.Redis(host='redis', port=6379, decode_responses=True)
client = pymongo.MongoClient("mongodb://mongo:27017")
db = client.assessment

def process_writes():
    while True:
        # Read a batch of 50 messages
        messages = r.xread({ "write_stream": "0" }, count=50, block=1000)
        
        if messages:
            stream_name, entries = messages[0]
            batch = []
            ids = []
            
            for entry_id, data in entries:
                batch.append(json.loads(data['data']))
                ids.append(entry_id)
            
            # Perform a Bulk Write to Mongo (1 IOPS instead of 50!)
            if batch:
                db.data.insert_many(batch)
                r.xdel("write_stream", *ids)
        
        # Artificial sleep to stay under the 100 IOPS cap
        time.sleep(0.5) 

if __name__ == "__main__":
    process_writes()
