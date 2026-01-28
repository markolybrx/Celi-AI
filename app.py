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
if 'upstash' in redis_url or 'rediss' in redis_url:
    if redis_url.startswith('redis://'): redis_url = redis_url.replace('redis://', 'rediss://', 1)
    app.config['SESSION_REDIS'] = redis.from_url(redis_url, ssl_cert_reqs=None)
else:
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)

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
    except Exception as e: print(f"❌ Memory Core Error: {e}")

# --- CONFIG: AI CORE ---
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    try: 
        # Clean key just in case
        clean_key = api_key.strip().replace("'", "").replace('"', "")
        genai.configure(api_key=clean_key)
        print("✅ Gemini AI Core Connected")
    except Exception as e:
        print(f"❌ Gemini AI Connection Failed: {e}")

# ==================================================
#           THE ECHO PROTOCOL (MEMORY)
# ==================================================

def get_embedding(text):
    try:
        if not text or len(text) < 5: return None
        # Use stable embedding model
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
#                 HELPER FUNCTIONS
# ==================================================

def generate_analysis(entry_text):
    """Generates psychological analysis for the Archive Modal."""
    # V12.18: Updated to Gemini 2.5 Flash
    candidates = ["gemini-2.5-flash", "gemini-2.0-flash"]
    
    for m in candidates:
        try:
            model = genai.GenerativeModel(m)
            prompt = f"Provide a warm, human-like psychological insight about this journal entry. Speak directly to 'You'. Keep it to 1 or 2 sentences max. Entry: {entry_text}"
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Analysis Error ({m}): {e}")
            continue
            
    return "Analysis unavailable due to signal interference."

def generate_summary(entry_text):
    """Generates a natural 1-2 sentence recap for the Calendar Echo."""
    # V12.18: Updated to Gemini 2.5 Flash
    candidates = ["gemini-2.5-flash", "gemini-2.0-flash"]
    
    for m in candidates:
        try:
            model = genai.GenerativeModel(m)
            prompt = f"Write a 1 or 2 sentence recap of this entry addressed to 'You', as if you are a supportive friend remembering it. Do not start with 'You mentioned'. Entry: {entry_text}"
            response = model.generate_content(prompt)
            return response.text.strip().replace('"', '').replace("'", "")
        except:
            continue
            
    return entry_text[:50] + "..."

def generate_constellation_name(entries_text):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"Here are 7 days of journal entries. Give them a mystical 'Constellation Name' (e.g., 'The Week of Rain'). Just the name. Entries: {entries_text}"
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '').replace("'", "")
    except:
        return "Unknown Constellation"

def generate_with_media(msg, media_bytes=None, media_mime=None, is_void=False, context_memories=[]):
    """Main generation logic for Celi/Void responses with Fallback."""
    # V12.18: Updated Candidate List for 2026 Timeline
    candidates = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    
    memory_block = ""
    if context_memories:
        memory_block = "\n\nRELEVANT PAST MEMORIES (Use these to connect patterns, but don't repeat them explicitly):\n"
        for mem in context_memories:
            memory_block += f"- [{mem['date']}]: {mem['full_message']}\n"
    
    base_instruction = "You are 'The Void'. Infinite, safe emptiness. Absorb pain." if is_void else "You are Celi. Analyze the user's day based on their text and/or image. Be warm and observant. Keep responses concise (under 3 sentences)."
    system_instruction = base_instruction + memory_block
    
    # Construct Content Payload
    content = [msg]
    has_media = False
    if media_bytes and media_mime and 'image' in media_mime:
        has_media = True
        content.append({'mime_type': media_mime, 'data': media_bytes})

    # Try generating with media first
    for m in candidates:
        try:
            model = genai.GenerativeModel(m, system_instruction=system_instruction)
            response = model.generate_content(content)
            if not response.text: raise Exception("Empty response")
            return response.text.strip()
        except Exception as e:
            print(f"DEBUG: Model Error ({m}): {e}")
            continue

    # FALLBACK: If media generation failed, try text-only
    if has_media:
        print("⚠️ Media processing failed. Retrying with text-only fallback...")
        try:
            # Fallback to lite model for speed/stability
            model = genai.GenerativeModel("gemini-2.5-flash-lite", system_instruction=system_instruction)
            response = model.generate_content(msg + " [Image attached but signal weak]")
            return response.text.strip()
        except Exception as e:
            print(f"Fallback Error: {e}")

    return "Signal Lost. Visual/Text processing failed. Please check your API Key or connection."

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
        if users_col is None: return jsonify({"status": "error", "error": "Database Offline"})
        user = users_col.find_one({"username": username})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            return jsonify({"status": "success"})
        else: return jsonify({"status": "error", "error": "Invalid Credentials"}), 401
    except Exception as e: return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login_page'))

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/api/media/<file_id>')
def get_media(file_id):
    try:
        if fs is None: return "Database Error", 500
        grid_out = fs.get(ObjectId(file_id))
        return Response(grid_out.read(), mimetype=grid_out.content_type)
    except: return "File not found", 404

# --- PROFILE UPDATES ---
@app.route('/api/update_pfp', methods=['POST'])
def update_pfp():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Auth required"}), 401
    try:
        file = request.files['pfp']
        if file:
            file_id = fs.put(file.read(), filename=f"pfp_{session['user_id']}", content_type=file.mimetype)
            pfp_url = f"/api/media/{file_id}"
            users_col.update_one({"user_id": session['user_id']}, {"$set": {"profile_pic": pfp_url}})
            return jsonify({"status": "success", "url": pfp_url})
        return jsonify({"status": "error", "message": "No file"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Auth required"}), 401
    try:
        data = request.json
        updates = {}
        if 'first_name' in data: updates['first_name'] = data['first_name']
        if 'last_name' in data: updates['last_name'] = data['last_name']
        if 'aura_color' in data: updates['aura_color'] = data['aura_color']
        
        if updates:
            users_col.update_one({"user_id": session['user_id']}, {"$set": updates})
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "No changes detected"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/update_security', methods=['POST'])
def update_security():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Auth required"}), 401
    try:
        data = request.json
        updates = {}
        if 'new_password' in data:
            updates['password_hash'] = generate_password_hash(data['new_password'])
        if 'new_secret_a' in data and 'new_secret_q' in data:
            updates['secret_question'] = data['new_secret_q']
            updates['secret_answer_hash'] = generate_password_hash(data['new_secret_a'].lower().strip())
        
        if updates:
            users_col.update_one({"user_id": session['user_id']}, {"$set": updates})
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "No data"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/register', methods=['POST'])
def register():
    try:
        if users_col is None: return jsonify({"status": "error", "error": "Database Offline"})
        data = request.json
        if users_col.find_one({"username": data['reg_username']}): return jsonify({"status": "error", "error": "Username taken"})
        new_user = {
            "user_id": str(uuid.uuid4()), "username": data['reg_username'], "password_hash": generate_password_hash(data['reg_password']),
            "first_name": data['fname'], "last_name": data['lname'], "dob": data['dob'], "aura_color": data.get('fav_color', '#00f2fe'),
            "secret_question": data['secret_question'], "secret_answer_hash": generate_password_hash(data['secret_answer'].lower().strip()),
            "rank": "Observer III", "rank_index": 0, "stardust": 0, "profile_pic": data.get('profile_pic', ''), "joined_at": datetime.now()
        }
        users_col.insert_one(new_user)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "error": str(e)})

@app.route('/api/data')
def get_data():
    if 'user_id' not in session: return jsonify({"status": "guest"}), 401
    if users_col is None: return jsonify({"status": "error"}), 500
    user = users_col.find_one({"user_id": session['user_id']})
    if not user: return jsonify({"status": "error"}), 404
    
    rank_info = get_rank_meta(user.get('rank_index', 0))
    progression_tree = get_all_ranks_data()
    max_dust = rank_info['req']
    current_dust = user.get('stardust', 0)
    
    history_cursor = history_col.find({"user_id": session['user_id']}, {'_id': 0, 'embedding': 0, 'media_file_id': 0, 'audio_file_id': 0}).sort("timestamp", 1).limit(50)
    loaded_history = {entry['timestamp']: entry for entry in history_cursor}

    return jsonify({
        "status": "user", 
        "username": user.get("username"), 
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name", ""),
        "user_id": user.get("user_id", ""),
        "aura_color": user.get("aura_color", "#00f2fe"),
        "secret_question": user.get("secret_question", "???"),
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
    cursor = history_col.find({"user_id": session['user_id']}, 
                              {'_id': 0, 'full_message': 0, 'reply': 0, 'embedding': 0, 'media_file_id': 0, 'audio_file_id': 0}).sort("timestamp", 1)
    stars = []
    for index, doc in enumerate(cursor):
        stars.append({
            "id": doc['timestamp'], "date": doc['date'], "summary": doc.get('summary', '...'),
            "type": "void" if doc.get('mode') == 'rant' else "journal",
            "has_media": doc.get('has_media', False), "has_audio": doc.get('has_audio', False),
            "group": index // 7, "constellation_name": doc.get('constellation_name', None), "index": index
        })
    return jsonify(stars)

@app.route('/api/star_detail', methods=['POST'])
def star_detail():
    if 'user_id' not in session: return jsonify({"error": "Auth"})
    data = request.json
    timestamp = data.get('id')
    entry = history_col.find_one({"user_id": session['user_id'], "timestamp": timestamp}, {'_id': 0, 'embedding': 0})
    if not entry: return jsonify({"error": "Not found"})
    
    # Lazy Load Analysis
    analysis = entry.get('ai_analysis')
    if not analysis:
        analysis = generate_analysis(entry.get('full_message', ''))
        history_col.update_one({"user_id": session['user_id'], "timestamp": timestamp}, {"$set": {"ai_analysis": analysis}})
    
    image_url = f"/api/media/{entry['media_file_id']}" if entry.get('media_file_id') else None
    audio_url = f"/api/media/{entry['audio_file_id']}" if entry.get('audio_file_id') else None

    return jsonify({
        "date": entry['date'], 
        "analysis": analysis, 
        "summary": entry.get('summary', ''),
        "image_url": image_url, 
        "audio_url": audio_url, 
        "mode": entry.get('mode', 'journal')
    })

@app.route('/api/process', methods=['POST'])
def process():
    if 'user_id' not in session: return jsonify({"reply": "Session Expired"}), 401
    try:
        msg = request.form.get('message', '')
        mode = request.form.get('mode', 'journal')
        image_file = request.files.get('media')
        audio_file = request.files.get('audio')
        timestamp = str(datetime.now().timestamp())
        
        # GridFS Storage
        media_id = fs.put(image_file.read(), filename=f"img_{timestamp}", content_type=image_file.mimetype) if image_file else None
        audio_id = fs.put(audio_file, filename=f"aud_{timestamp}", content_type=audio_file.mimetype) if audio_file else None
        image_bytes = fs.get(media_id).read() if media_id else None
        image_mime = image_file.mimetype if image_file else None

        # Vector Context
        past_memories = []
        embedding = None
        if msg and len(msg) > 10:
            past_memories = find_similar_memories(session['user_id'], msg)
            embedding = get_embedding(msg)

        reply = "..."
        reward_result = process_daily_rewards(users_col, session['user_id'], msg)
        
        # AI Generation
        if mode == 'rant':
            reply = generate_with_media(msg, image_bytes, image_mime, is_void=True, context_memories=past_memories)
        else:
            if session.get('awaiting_void_confirm', False):
                if any(x in msg.lower() for x in ["yes", "sure", "ok"]): 
                    reply, command, session['awaiting_void_confirm'] = "Understood. Opening Void...", "switch_to_void", False
                else: 
                    session['awaiting_void_confirm'] = False
                    reply = generate_with_media(f"User declined void. Respond: {msg}", image_bytes, image_mime, False)
            else:
                reply = generate_with_media(msg, image_bytes, image_mime, False, context_memories=past_memories)
                if "open The Void" in reply: session['awaiting_void_confirm'] = True

        # Generate Natural Summary for Echo
        summary_text = generate_summary(msg) if msg else "Visual Entry"

        constellation_name = None
        if reward_result.get('event') == 'constellation_complete':
            last_entries = history_col.find({"user_id": session['user_id']}, {'full_message': 1}).sort("timestamp", -1).limit(6)
            text_block = msg + " " + " ".join([e.get('full_message','') for e in last_entries])
            constellation_name = generate_constellation_name(text_block)

        history_col.insert_one({
            "user_id": session['user_id'],
            "timestamp": timestamp,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": summary_text,
            "full_message": msg,
            "reply": reply,
            "ai_analysis": None,
            "mode": mode,
            "has_media": bool(media_id), "media_file_id": media_id,
            "has_audio": bool(audio_id), "audio_file_id": audio_id,
            "constellation_name": constellation_name,
            "is_valid_star": reward_result['awarded'],
            "embedding": embedding
        })
        
        command = None
        level_check = update_rank_check(users_col, session['user_id'])
        if level_check == "level_up": command = "level_up"; reply += f"\n\n[System]: Level Up! {reward_result.get('message', '')}"
        elif reward_result['awarded']: command = "daily_reward"; reply += f"\n\n[System]: {reward_result['message']}"
        if constellation_name: reply += f"\n[Cosmos]: A new constellation has formed: '{constellation_name}'"

        return jsonify({"reply": reply, "command": command})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"Signal Lost. Visual/Text processing failed."}), 500

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    if 'user_id' not in session: 
        return jsonify({"status": "error", "message": "No active session"}), 401
    try:
        user_id = session['user_id']
        history_col.delete_many({"user_id": user_id})
        users_col.delete_one({"user_id": user_id})
        session.clear()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/sw.js')
def service_worker(): return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json', mimetype='application/json')

if __name__ == '__main__': app.run(debug=True, port=5000)
