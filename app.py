import os
import logging
import traceback
import uuid
import json
import certifi
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
app.config['SESSION_REDIS'] = db.redis_client 

server_session = Session(app)

# --- CONFIG: AI CORE ---
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    clean_key = api_key.strip().replace("'", "").replace('"', "")
    genai.configure(api_key=clean_key)

# ==================================================
#           HELPER: JSON SERIALIZER
# ==================================================
def serialize_doc(doc):
    """Converts MongoDB documents to JSON-safe dictionaries."""
    if not doc: return None
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    
    # Convert ObjectId to string
    if '_id' in doc: doc['_id'] = str(doc['_id'])
    if 'user_id' in doc and isinstance(doc['user_id'], ObjectId): doc['user_id'] = str(doc['user_id'])
    
    # Recursively handle other ObjectIds
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc

# ==================================================
#           SYNC HELPER (Immediate Reply)
# ==================================================

def generate_immediate_reply(msg, media_bytes=None, media_mime=None, is_void=False, context_memories=[]):
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
    if not query_text or db.history_col is None: return []
    try:
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

        media_id = db.fs.put(image_file.read(), filename=f"img_{timestamp}", content_type=image_file.mimetype) if image_file else None
        audio_id = db.fs.put(audio_file, filename=f"aud_{timestamp}", content_type=audio_file.mimetype) if audio_file else None
        
        image_bytes = None
        if media_id:
            image_bytes = db.fs.get(media_id).read()

        past_memories = []
        if msg and len(msg) > 10:
            past_memories = find_similar_memories_sync(session['user_id'], msg)

        reward_result = process_daily_rewards(db.users_col, session['user_id'], msg)

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

        db.history_col.insert_one({
            "user_id": session['user_id'],
            "timestamp": timestamp,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": "Processing...",  
            "full_message": msg,
            "reply": reply,
            "ai_analysis": None,         
            "mode": mode,
            "has_media": bool(media_id), "media_file_id": media_id,
            "has_audio": bool(audio_id), "audio_file_id": audio_id,
            "constellation_name": None,
            "is_valid_star": reward_result['awarded'],
            "embedding": None
        })

        process_entry_analysis.delay(timestamp, msg, session['user_id'])

        if reward_result.get('event') == 'constellation_complete':
            last_entries = db.history_col.find({"user_id": session['user_id']}, {'full_message': 1}).sort("timestamp", -1).limit(6)
            text_block = msg + " " + " ".join([e.get('full_message','') for e in last_entries])
            generate_constellation_name_task.delay(session['user_id'], timestamp, text_block)

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

@app.route('/api/data')
def get_data():
    if 'user_id' not in session: return jsonify({"status": "guest"}), 401
    
    user = db.users_col.find_one({"user_id": session['user_id']})
    if not user: return jsonify({"status": "error"}), 404
    user = serialize_doc(user) 

    rank_info = get_rank_meta(user.get('rank_index', 0))
    progression_tree = get_all_ranks_data()
    max_dust = rank_info['req']
    current_dust = user.get('stardust', 0)

    history_cursor = db.history_col.find({"user_id": session['user_id']}, {'embedding': 0}).sort("timestamp", 1).limit(50)
    history_list = [serialize_doc(doc) for doc in history_cursor]
    loaded_history = {entry['timestamp']: entry for entry in history_list}

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
    cursor = db.history_col.find({"user_id": session['user_id']}, 
                              {'_id': 0, 'full_message': 0, 'reply': 0, 'embedding': 0}).sort("timestamp", 1)
    stars = []
    for index, doc in enumerate(cursor):
        doc = serialize_doc(doc)
        stars.append({
            "id": doc['timestamp'], "date": doc['date'], 
            "summary": doc.get('summary', 'Processing...'), 
            "type": "void" if doc.get('mode') == 'rant' else "journal",
            "has_media": doc.get('has_media', False),
            "group": index // 7, "constellation_name": doc.get('constellation_name', None), "index": index
        })
    return jsonify(stars)

@app.route('/api/star_detail', methods=['POST'])
def star_detail():
    if 'user_id' not in session: return jsonify({"error": "Auth"})
    timestamp = request.json.get('id')
    entry = db.history_col.find_one({"user_id": session['user_id'], "timestamp": timestamp}, {'embedding': 0})
    if not entry: return jsonify({"error": "Not found"})
    
    entry = serialize_doc(entry)

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

@app.route('/api/media/<file_id>')
def get_media(file_id):
    try:
        if db.fs is None: return "Database Error", 500
        grid_out = db.fs.get(ObjectId(file_id))
        return Response(grid_out.read(), mimetype=grid_out.content_type)
    except: return "File not found", 404

@app.route('/api/update_pfp', methods=['POST'])
def update_pfp():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    try:
        file = request.files['pfp']
        if file:
            file_id = db.fs.put(file.read(), filename=f"pfp_{session['user_id']}", content_type=file.mimetype)
            pfp_url = f"/api/media/{file_id}"
            db.users_col.update_one({"user_id": session['user_id']}, {"$set": {"profile_pic": pfp_url}})
            return jsonify({"status": "success", "url": pfp_url})
        return jsonify({"status": "error"})
    except: return jsonify({"status": "error"})

# --- RESTORED ROUTES ---

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        if db.users_col.find_one({"username": data['reg_username']}): 
            return jsonify({"status": "error", "error": "Username taken"})
        
        new_user = {
            "user_id": str(uuid.uuid4()), 
            "username": data['reg_username'], 
            "password_hash": generate_password_hash(data['reg_password']),
            "first_name": data['fname'], 
            "last_name": data['lname'], 
            "dob": data['dob'], 
            "aura_color": data.get('fav_color', '#00f2fe'),
            "secret_question": data['secret_question'], 
            "secret_answer_hash": generate_password_hash(data['secret_answer'].lower().strip()),
            "rank": "Observer III", "rank_index": 0, "stardust": 0, 
            "profile_pic": data.get('profile_pic', ''), 
            "joined_at": datetime.now()
        }
        db.users_col.insert_one(new_user)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "error": str(e)})

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
            db.users_col.update_one({"user_id": session['user_id']}, {"$set": updates})
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "No changes"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/update_security', methods=['POST'])
def update_security():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Auth required"}), 401
    try:
        data = request.json
        updates = {}
        if 'new_password' in data: 
            updates['password_hash'] = generate_password_hash(data['new_password'])
        if 'new_secret_a' in data:
            updates['secret_question'] = data['new_secret_q']
            updates['secret_answer_hash'] = generate_password_hash(data['new_secret_a'].lower().strip())
            
        if updates:
            db.users_col.update_one({"user_id": session['user_id']}, {"$set": updates})
            return jsonify({"status": "success"})
        return jsonify({"status": "error"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    try:
        db.history_col.delete_many({"user_id": session['user_id']})
        db.users_col.delete_one({"user_id": session['user_id']})
        session.clear()
        return jsonify({"status": "success"})
    except: return jsonify({"status": "error"}), 500

# --- STATIC FILES ---
@app.route('/sw.js')
def service_worker(): return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json', mimetype='application/json')

if __name__ == '__main__': app.run(debug=True, port=5000)