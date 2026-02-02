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
from datetime import datetime
import google.generativeai as genai
from pymongo import MongoClient

# --- IMPORT RANK LOGIC ---
from rank_system import process_daily_rewards, update_rank_check, get_rank_meta, get_all_ranks_data

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

# --- CONFIG: SECRET & REDIS ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'celi_super_secret_key_999')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
try:
    if 'upstash' in redis_url or 'rediss' in redis_url:
        if redis_url.startswith('redis://'):
            redis_url = redis_url.replace('redis://', 'rediss://', 1)
        app.config['SESSION_REDIS'] = redis.from_url(redis_url, ssl_cert_reqs=None)
    else:
        app.config['SESSION_REDIS'] = redis.from_url(redis_url)
except Exception as e:
    print(f"⚠️ Redis connection error: {e}")
    app.config['SESSION_REDIS'] = None

server_session = Session(app)

# --- CONFIG: MONGODB & GRIDFS ---
mongo_uri = os.environ.get("MONGO_URI")
db, users_col, history_col, fs = None, None, None, None

if mongo_uri:
    try:
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        db = client['celi_journal_db']
        users_col = db['users']
        history_col = db['history']
        fs = gridfs.GridFS(db)
        print("✅ Memory Core (MongoDB + GridFS + Vectors) Connected")
    except Exception as e:
        print(f"❌ Memory Core Error: {e}")

# --- CONFIG: AI CORE (Gemini 2.5 Flash) ---
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    try: 
        clean_key = api_key.strip().replace("'", "").replace('"', "")
        genai.configure(api_key=clean_key)
        print("✅ Gemini AI Core Connected")
    except Exception as e:
        print(f"❌ Gemini AI Connection Failed: {e}")
else:
    print("⚠️ GEMINI_API_KEY not set. AI functions will fail.")

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
                "summary": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]
    try:
        results = list(history_col.aggregate(pipeline))
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
        except Exception as e:
            print(f"Analysis Error ({m}): {e}")
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
        memory_block = "\n\nRELEVANT PAST MEMORIES:\n"
        for mem in context_memories:
            memory_block += f"- [{mem['date']}]: {mem['full_message']}\n"

    base_instruction = "You are 'The Void'. Infinite, safe emptiness. Absorb pain." if is_void else "You are Celi. Analyze the user's day. Be warm and concise."
    system_instruction = base_instruction + memory_block

    content = [msg]
    has_media = False
    if media_bytes and media_mime and 'image' in media_mime:
        has_media = True
        content.append({'mime_type': media_mime, 'data': media_bytes})

    for m in candidates:
        try:
            model = genai.GenerativeModel(m, system_instruction=system_instruction)
            response = model.generate_content(content)
            if not response.text: raise Exception("Empty response")
            return response.text.strip()
        except Exception as e:
            print(f"DEBUG: Model Error ({m}): {e}")
            continue

    if has_media:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash-lite", system_instruction=system_instruction)
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
        username, password = request.form.get('username'), request.form.get('password')
        if users_col is None: return jsonify({"status": "error", "error": "Database Offline"})
        user = users_col.find_one({"username": username})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "error": "Invalid Credentials"}), 401
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

# ... (Keep the rest of your routes exactly the same, including /api/update_pfp, /api/update_profile, /api/register, /api/process, etc.)

# ==================================================
#                  APP RUN
# ==================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)