import os
import logging
import traceback
import uuid
import json
from bson.objectid import ObjectId
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, Response
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import google.generativeai as genai

# --- IMPORT DATABASE & TASKS ---
import database as db
from tasks import process_entry_analysis, generate_constellation_name_task
from rank_system import process_daily_rewards, update_rank_check, get_rank_meta, get_all_ranks_data

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

# --- CONFIG ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'celi_super_secret_key_999')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = db.redis_client # Use shared connection

server_session = Session(app)

# --- CONFIG: AI CORE (For Immediate Chat Replies) ---
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    clean_key = api_key.strip().replace("'", "").replace('"', "")
    genai.configure(api_key=clean_key)

# ==================================================
#           SYNC HELPER (Immediate Reply)
# ==================================================
# We keep this SYNC because we want the user to get a reply instantly.
# Everything else (Summary, Analysis, Embeddings) moves to Celery.

def generate_immediate_reply(msg, media_bytes=None, media_mime=None, is_void=False, context_memories=[]):
    """Generates the immediate chat response."""
    candidates = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    
    memory_block = ""
    if context_memories:
        memory_block = "\n\nRELEVANT PAST MEMORIES:\n"
        for mem in context_memories:
            memory_block += f"- [{mem['date']}]: {mem['full_message']}\n"

    base_instruction = "You are 'The Void'. Infinite, safe emptiness. Absorb pain." if is_void else "You are Celi. Analyze the user's day based on their text and/or image. Be warm and observant. Keep responses concise (under 3 sentences)."
    system_instruction = base_instruction + memory_block

    content = [msg]
    if media_bytes and media_mime and 'image' in media_mime:
        content.append({'mime_type': media_mime, 'data': media_bytes})

    for m in candidates:
        try:
            model = genai.GenerativeModel(m, system_instruction=system_instruction)
            response = model.generate_content(content)
            return response.text.strip()
        except: continue
    
    return "Signal Lost. I heard you, but I cannot speak right now."

def find_similar_memories_sync(user_id, query_text):
    """
    Lightweight sync vector search. 
    If this is too slow, we can remove it, but it usually takes <1s.
    """
    if not query_text or db.history_col is None: return []
    try:
        # We need an embedding for the query. 
        # Since this is blocking, we use the fastest model or skip if needed.
        result = genai.embed_content(model="models/text-embedding-004", content=query_text)
        query_vector = result['embedding']
        
        pipeline = [
            {"$vectorSearch": {
                "index": "vector_index", "path": "embedding", "queryVector": query_vector,
                "numCandidates": 50, "limit": 3, "filter": {"user_id": user_id}
            }},
            {"$project": {"_id": 0, "full_message": 1, "date": 1, "score": {"$meta": "vectorSearchScore"}}}
        ]
        results = list(db.history_col.aggregate(pipeline))
        return [r for r in results if r['score'] > 0.65] 
    except:
        return []

# ==================================================
#                 ROUTES
# ==================================================

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET': return redirect(url_for('index')) if 'user_id' in session else render_template('auth.html')
    try:
        username, password = request.form.get('username'), request.form.get('password')
        if db.users_col is None: return jsonify({"status": "error", "error": "Database Offline"})
        user = db.users_col.find_one({"username": username})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            return jsonify({"status": "success"})
        else: return jsonify({"status": "error", "error": "Invalid Credentials"}), 401
    except Exception as e: return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login_page'))

@app.route('/api/process', methods=['POST'])
def process():
    if 'user_id' not in session: return jsonify({"reply": "Session Expired"}), 401
    try:
        msg = request.form.get('message', '')
        mode = request.form.get('mode', 'journal')
        image_file = request.files.get('media')
        audio_file = request.files.get('audio')
        timestamp = str(datetime.now().timestamp())

        # 1. Handle Media (Sync - Fast)
        media_id = db.fs.put(image_file.read(), filename=f"img_{timestamp}", content_type=image_file.mimetype) if image_file else None
        audio_id = db.fs.put(audio_file, filename=f"aud_{timestamp}", content_type=audio_file.mimetype) if audio_file else None
        
        image_bytes = None
        if media_id:
            image_bytes = db.fs.get(media_id).read()
            image_mime = image_file.mimetype

        # 2. Context Retrieval (Sync - Optional, can disable if slow)
        past_memories = []
        if msg and len(msg) > 10:
            past_memories = find_similar_memories_sync(session['user_id'], msg)

        # 3. Calculate Rewards (Sync - Very Fast)
        reward_result = process_daily_rewards(db.users_col, session['user_id'], msg)

        # 4. Generate Immediate Reply (Sync - 1-2s)
        reply = "..."
        if mode == 'rant':
            reply = generate_immediate_reply(msg, image_bytes, image_file.mimetype if image_file else None, True, past_memories)
        else:
            if session.get('awaiting_void_confirm', False):
                if any(x in msg.lower() for x in ["yes", "sure", "ok"]): 
                    reply, command, session['awaiting_void_confirm'] = "Understood. Opening Void...", "switch_to_void", False
                else: 
                    session['awaiting_void_confirm'] = False
                    reply = generate_immediate_reply(f"User declined void. Respond: {msg}", image_bytes, image_file.mimetype if image_file else None, False)
            else:
                reply = generate_immediate_reply(msg, image_bytes, image_file.mimetype if image_file else None, False, past_memories)
                if "open The Void" in reply: session['awaiting_void_confirm'] = True

        # 5. Save Initial Record (Sync)
        # We save "Processing..." for summary/analysis so the UI has something to show immediately
        db.history_col.insert_one({
            "user_id": session['user_id'],
            "timestamp": timestamp,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": "Processing...",  # Placeholder
            "full_message": msg,
            "reply": reply,
            "ai_analysis": None,         # Placeholder
            "mode": mode,
            "has_media": bool(media_id), "media_file_id": media_id,
            "has_audio": bool(audio_id), "audio_file_id": audio_id,
            "constellation_name": None,
            "is_valid_star": reward_result['awarded'],
            "embedding": None
        })

        # 6. TRIGGER BACKGROUND TASKS (Async - Instant)
        # This offloads the heavy lifting (Embedding, Summary, Analysis)
        process_entry_analysis.delay(timestamp, msg, session['user_id'])

        # Check for Constellation Event
        if reward_result.get('event') == 'constellation_complete':
            last_entries = db.history_col.find({"user_id": session['user_id']}, {'full_message': 1}).sort("timestamp", -1).limit(6)
            text_block = msg + " " + " ".join([e.get('full_message','') for e in last_entries])
            generate_constellation_name_task.delay(session['user_id'], timestamp, text_block)

        # 7. Construct Response
        command = None
        level_check = update_rank_check(db.users_col, session['user_id'])
        
        system_msg = ""
        if level_check == "level_up": 
            command = "level_up"
            system_msg = f"\n\n[System]: Level Up! {reward_result.get('message', '')}"
        elif reward_result['awarded']: 
            command = "daily_reward"
            system_msg = f"\n\n[System]: {reward_result['message']}"

        return jsonify({"reply": reply + system_msg, "command": command})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"Signal Lost. Processing failed."}), 500

# --- DATA ENDPOINTS ---
@app.route('/api/data')
def get_data():
    if 'user_id' not in session: return jsonify({"status": "guest"}), 401
    user = db.users_col.find_one({"user_id": session['user_id']})
    if not user: return jsonify({"status": "error"}), 404

    rank_info = get_rank_meta(user.get('rank_index', 0))
    progression_tree = get_all_ranks_data()
    max_dust = rank_info['req']
    current_dust = user.get('stardust', 0)

    history_cursor = db.history_col.find({"user_id": session['user_id']}, {'_id': 0, 'embedding': 0}).sort("timestamp", 1).limit(50)
    loaded_history = {entry['timestamp']: entry for entry in history_cursor}

    return jsonify({
        "status": "user", 
        "username": user.get("username"), 
        "rank": user.get("rank", "Observer III"), 
        "rank_index": user.get("rank_index", 0),
        "rank_progress": (current_dust/max_dust)*100 if max_dust>0 else 0,
        "rank_psyche": rank_info.get("psyche", "Unknown"), 
        "rank_desc": rank_info.get("desc", ""),
        "current_svg": rank_info.get("svg"), 
        "current_color": rank_info.get("color"),
        "stardust_current": current_dust, 
        "stardust_max": max_dust,
        "history": loaded_history, 
        "profile_pic": user.get("profile_pic", ""),
        "progression_tree": progression_tree
    })

@app.route('/api/galaxy_map')
def galaxy_map():
    if 'user_id' not in session: return jsonify([])
    cursor = db.history_col.find({"user_id": session['user_id']}, 
                              {'_id': 0, 'full_message': 0, 'reply': 0, 'embedding': 0}).sort("timestamp", 1)
    stars = []
    for index, doc in enumerate(cursor):
        stars.append({
            "id": doc['timestamp'], "date": doc['date'], 
            "summary": doc.get('summary', 'Processing...'), # Handling async lag
            "type": "void" if doc.get('mode') == 'rant' else "journal",
            "has_media": doc.get('has_media', False),
            "group": index // 7, "constellation_name": doc.get('constellation_name', None), "index": index
        })
    return jsonify(stars)

@app.route('/api/star_detail', methods=['POST'])
def star_detail():
    if 'user_id' not in session: return jsonify({"error": "Auth"})
    timestamp = request.json.get('id')
    entry = db.history_col.find_one({"user_id": session['user_id'], "timestamp": timestamp}, {'_id': 0, 'embedding': 0})
    if not entry: return jsonify({"error": "Not found"})

    # If analysis is still missing (very rare), we say "Processing"
    analysis = entry.get('ai_analysis', "Psychological analysis is being generated...")
    
    image_url = f"/api/media/{entry['media_file_id']}" if entry.get('media_file_id') else None
    audio_url = f"/api/media/{entry['audio_file_id']}" if entry.get('audio_file_id') else None

    return jsonify({
        "date": entry['date'], 
        "analysis": analysis, 
        "summary": entry.get('summary', 'Processing...'),
        "image_url": image_url, 
        "audio_url": audio_url, 
        "mode": entry.get('mode', 'journal')
    })

# Add other helper routes (media, pfp, etc.) back here as needed using db.fs and db.users_col

if __name__ == '__main__': app.run(debug=True, port=5000)