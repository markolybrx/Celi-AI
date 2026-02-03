import os
import logging
import traceback
import certifi
import uuid
import redis
import ssl
import json
import gridfs
from bson.objectid import ObjectId
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, Response
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import google.generativeai as genai
from pymongo import MongoClient

# --- IMPORT RANK LOGIC ---
# Ensure rank_system.py is in the same directory!
try:
    from rank_system import process_daily_rewards, update_rank_check, get_rank_meta, get_all_ranks_data
except ImportError:
    # Fallback if file is missing during initial setup to prevent crash
    def process_daily_rewards(uid, db): return {}
    def update_rank_check(uid, col, hist): return None, None
    def get_rank_meta(pts): return "Novice", "Star", 1
    def get_all_ranks_data(): return []

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

# --- CONFIG: SECRET & REDIS ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'celi_super_secret_key_999')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 1 day

redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
try:
    # Vercel/Upstash Redis usually requires SSL modification
    if 'upstash' in redis_url or 'rediss' in redis_url:
        if redis_url.startswith('redis://'):
            redis_url = redis_url.replace('redis://', 'rediss://', 1)
        app.config['SESSION_REDIS'] = redis.from_url(redis_url, ssl_cert_reqs=None)
    else:
        app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    print("✅ Redis Session Store Connected")
except Exception as e:
    print(f"⚠️ Redis connection error: {e}. Falling back to filesystem sessions (Note: ephemeral on Vercel).")
    app.config['SESSION_TYPE'] = 'filesystem'

server_session = Session(app)

# --- CONFIG: MONGODB & GRIDFS ---
# Try getting the variable by the name we set, OR the default Vercel name
mongo_uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")

db, users_col, history_col, fs = None, None, None, None

if mongo_uri:
    try:
        # The tlsCAFile=certifi.where() is CRITICAL for Vercel
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        
        # Force a connection check to see if it actually works
        client.admin.command('ping')
        
        db = client['celi_journal_db']
        users_col = db['users']
        history_col = db['history']
        fs = gridfs.GridFS(db)
        print("✅ Memory Core (MongoDB + GridFS + Vectors) Connected")
    except Exception as e:
        print(f"❌ Memory Core Error: {e}")
        # Print the URI (masked) to logs to see if it's even finding it
        if mongo_uri:
            print(f"DEBUG: URI found but failed. Length: {len(mongo_uri)}")
        else:
            print("DEBUG: No URI found in environment variables.")
else:
    print("❌ Critical: No MONGO_URI or MONGODB_URI found in environment variables.")


# ==================================================
#           MEMORY / ECHO PROTOCOL
# ==================================================

def get_embedding(text):
    try:
        if not text or len(text) < 5: return None
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document",
            title="Journal Entry"
        )
        return result['embedding']
    except Exception as e:
        print(f"Embedding Error: {e}")
        return None

def find_similar_memories(user_id, query_text):
    if not query_text or history_col is None: return []
    query_vector = get_embedding(query_text)
    if not query_vector: return []

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": 50,
                "limit": 3,
                "filter": {"user_id": user_id}
            }
        },
        {
            "$project": {
                "_id": 0,
                "full_message": 1,
                "date": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]
    try:
        results = list(history_col.aggregate(pipeline))
        # Filter for relevance
        return [r for r in results if r['score'] > 0.65] 
    except Exception as e:
        print(f"Vector Search Error: {e}")
        return []

# ==================================================
#                 AI HELPER FUNCTIONS
# ==================================================

def generate_analysis(entry_text):
    candidates = ["gemini-2.5-flash", "gemini-2.0-flash"]
    for m in candidates:
        try:
            model = genai.GenerativeModel(m)
            prompt = f"Provide a warm, human-like psychological insight about this journal entry. Speak directly to 'You'. Keep it 1-2 sentences. Entry: {entry_text}"
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            continue
    return "Analysis unavailable due to signal interference."

def generate_summary(entry_text):
    candidates = ["gemini-2.5-flash", "gemini-2.0-flash"]
    for m in candidates:
        try:
            model = genai.GenerativeModel(m)
            prompt = f"Write a 1-2 sentence recap of this entry addressed to 'You', as a supportive friend. Do not start with 'You mentioned'. Entry: {entry_text}"
            response = model.generate_content(prompt)
            return response.text.strip().replace('"', '').replace("'", "")
        except:
            continue
    return entry_text[:50] + "..."

def generate_constellation_name(entries_text):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"Here are 7 days of journal entries. Give them a mystical 'Constellation Name'. Just the name. Entries: {entries_text}"
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '').replace("'", "")
    except:
        return "Unknown Constellation"

def generate_with_media(msg, media_bytes=None, media_mime=None, is_void=False, context_memories=[]):
    candidates = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    
    memory_block = ""
    if context_memories:
        memory_block = "\n\n[RECALLED MEMORIES]:\n"
        for mem in context_memories:
            memory_block += f"- ({mem['date']}): {mem['full_message']}\n"

    base_instruction = (
        "You are 'The Void'. Infinite, safe emptiness. Absorb pain. " 
        if is_void else 
        "You are Celi: AI Journal. Friendly, empathetic, smart-casual, and witty. "
        "Support the user. Remember everything about them from the provided memories."
    )
    
    system_instruction = base_instruction + memory_block

    content = [msg]
    has_media = False
    if media_bytes and media_mime and 'image' in media_mime:
        has_media = True
        content.append({'mime_type': media_mime, 'data': media_bytes})

    # Try Primary Models
    for m in candidates:
        try:
            model = genai.GenerativeModel(m, system_instruction=system_instruction)
            response = model.generate_content(content)
            if response.text:
                return response.text.strip()
        except Exception as e:
            print(f"DEBUG: Model Error ({m}): {e}")
            continue

    # Fallback for Media
    if has_media:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
            response = model.generate_content(msg + " [Image attached but signal weak]")
            return response.text.strip()
        except Exception as e:
            print(f"Fallback Error: {e}")

    return "Signal Lost. Visual/Text processing failed. Check your API key or connection."

# ==================================================
#                     ROUTES
# ==================================================

@app.route('/')
def index():
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET': 
        return redirect(url_for('index')) if 'user_id' in session else render_template('auth.html')
    
    try:
        data = request.json if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')

        if users_col is None: return jsonify({"status": "error", "error": "Database Offline"}), 500
        
        user = users_col.find_one({"username": username})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            # Run daily check on login
            rewards = process_daily_rewards(user['user_id'], users_col)
            return jsonify({"status": "success", "rewards": rewards})
        
        return jsonify({"status": "error", "error": "Invalid Credentials"}), 401
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({"status": "error", "error": "Missing fields"}), 400
            
        if users_col.find_one({"username": username}):
            return jsonify({"status": "error", "error": "Username taken"}), 409
            
        user_id = str(uuid.uuid4())
        hashed_pw = generate_password_hash(password)
        
        new_user = {
            "user_id": user_id,
            "username": username,
            "password_hash": hashed_pw,
            "created_at": datetime.now(timezone.utc),
            "xp": 0,
            "level": 1,
            "rank": "Novice Stargazer",
            "bio": "A new traveler in the cosmos.",
            "profile_pic_id": None,
            "last_login": datetime.now(timezone.utc).isoformat()
        }
        users_col.insert_one(new_user)
        session['user_id'] = user_id
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/api/media/<file_id>')
def get_media(file_id):
    try:
        if fs is None: return "Database Error", 500
        grid_out = fs.get(ObjectId(file_id))
        return Response(grid_out.read(), mimetype=grid_out.content_type)
    except:
        return "File not found", 404

# --- MAIN CHAT PROCESSOR ---
@app.route('/api/process', methods=['POST'])
def process_message():
    if 'user_id' not in session:
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    try:
        user_id = session['user_id']
        message = request.form.get('message', '')
        mode = request.form.get('mode', 'normal') # 'normal' or 'void'
        
        # Handle Image Upload
        image_file = request.files.get('image')
        media_bytes = None
        media_mime = None
        file_id_str = None

        if image_file:
            media_bytes = image_file.read()
            media_mime = image_file.content_type
            # Store image in GridFS
            file_id = fs.put(media_bytes, filename=image_file.filename, content_type=media_mime)
            file_id_str = str(file_id)

        # 1. Retrieve Context
        context_memories = find_similar_memories(user_id, message)
        
        # 2. Generate AI Response
        is_void = (mode == 'void')
        ai_response_text = generate_with_media(message, media_bytes, media_mime, is_void, context_memories)

        # 3. Analyze & Embed
        analysis = generate_analysis(message)
        summary = generate_summary(message)
        embedding = get_embedding(message + " " + ai_response_text)

        # 4. Save to History
        entry = {
            "user_id": user_id,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "full_message": message,
            "ai_response": ai_response_text,
            "image_id": file_id_str,
            "analysis": analysis,
            "summary": summary,
            "embedding": embedding,
            "mode": mode
        }
        history_col.insert_one(entry)

        # 5. Check Rank Update (XP System)
        # Assuming 10 XP per entry
        users_col.update_one({"user_id": user_id}, {"$inc": {"xp": 10}})
        new_rank, rank_msg = update_rank_check(user_id, users_col, history_col)

        return jsonify({
            "status": "success",
            "response": ai_response_text,
            "analysis": analysis,
            "rank_update": rank_msg if new_rank else None
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/get_user_data')
def get_user_data():
    if 'user_id' not in session: return jsonify({"error": "No User"}), 401
    
    user = users_col.find_one({"user_id": session['user_id']}, {"_id": 0, "password_hash": 0})
    if not user: return jsonify({"error": "User missing"}), 404
    
    # --- FIX START: Align with new Rank System ---
    # The new system uses 'rank_index' to determine current rank
    current_index = user.get('rank_index', 0)
    
    # Get metadata from rank_system.py
    # We pass the INDEX, not the XP/Stardust
    rank_name, star_type, next_threshold = get_rank_meta(current_index)
    
    # Send standardized data to frontend
    user['rank'] = rank_name
    user['star_type'] = star_type
    user['next_level_xp'] = next_threshold
    # Ensure stardust is sent (frontend expects it)
    user['stardust'] = user.get('stardust', 0)
    # --- FIX END ---

    return jsonify(user)


@app.route('/api/get_history')
def get_history():
    if 'user_id' not in session: return jsonify([])
    # Get last 20 entries
    entries = list(history_col.find({"user_id": session['user_id']}).sort("date", -1).limit(20))
    for e in entries:
        e['_id'] = str(e['_id']) # Convert ObjectId to string
    return jsonify(entries[::-1]) # Reverse to show chronological

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    
    username = request.form.get('username')
    bio = request.form.get('bio')
    pfp_file = request.files.get('pfp')
    
    update_data = {}
    if username: update_data['username'] = username
    if bio: update_data['bio'] = bio
    
    if pfp_file:
        file_id = fs.put(pfp_file.read(), filename=pfp_file.filename, content_type=pfp_file.content_type)
        update_data['profile_pic_id'] = str(file_id)
        
    users_col.update_one({"user_id": session['user_id']}, {"$set": update_data})
    return jsonify({"status": "success"})

# ==================================================
#                  APP RUN
# ==================================================
# CRITICAL FOR VERCEL: Only run app.run() if executed directly.
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)