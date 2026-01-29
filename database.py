import os
import certifi
import gridfs
import redis
from pymongo import MongoClient

# --- GLOBAL CONNECTION OBJECTS ---
db = None
users_col = None
history_col = None
fs = None
redis_client = None

def init_db():
    """Initializes MongoDB and Redis connections."""
    global db, users_col, history_col, fs, redis_client

    # 1. MongoDB Connection
    mongo_uri = os.environ.get("MONGO_URI")
    if mongo_uri:
        try:
            client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
            db = client['celi_journal_db']
            users_col = db['users']
            history_col = db['history']
            fs = gridfs.GridFS(db)
            print("✅ [Database] MongoDB Connected")
        except Exception as e:
            print(f"❌ [Database] Mongo Error: {e}")

    # 2. Redis Connection
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    try:
        if 'upstash' in redis_url or 'rediss' in redis_url:
            if redis_url.startswith('redis://'): 
                redis_url = redis_url.replace('redis://', 'rediss://', 1)
            redis_client = redis.from_url(redis_url, ssl_cert_reqs=None)
        else:
            redis_client = redis.from_url(redis_url)
        print("✅ [Database] Redis Connected")
    except Exception as e:
        print(f"❌ [Database] Redis Error: {e}")

# Run initialization immediately on import
init_db()