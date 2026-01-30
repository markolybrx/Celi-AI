import os
import logging
import traceback
import uuid
import json
import time
from bson.objectid import ObjectId
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, Response
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import google.generativeai as genai

# --- IMPORT DATABASE ---
import database as db

# --- SAFETY IMPORT FOR TASKS ---
try:
    from tasks import process_entry_analysis, generate_constellation_name_task, generate_weekly_insight, generate_daily_trivia_task
except ImportError:
    print("⚠️  Warning: Tasks module not found. Background jobs disabled.")

from rank_system import process_daily_rewards, update_rank_check, get_rank_meta, get_all_ranks_data

# --- SETUP APP ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'celi_super_secret_key_999')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = db.redis_client 
server_session = Session(app)

# --- AI CONFIGURATION ---
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ CRITICAL: GEMINI_API_KEY is missing from environment variables!")
else:
    clean_key = api_key.strip().replace("'", "").replace('"', "")
    genai.configure(api_key=clean_key)
    print("✅ AI Core Online. Validating models...")
    try:
        # Diagnostic: Print available models to logs to debug 404 errors
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - Available: {m.name}")
    except Exception as e:
        print(f"⚠️ Could not list models: {e}")

# ==================================================
#           HELPER: JSON SERIALIZER
# ==================================================
def serialize_doc(doc):
    if not doc: return None
    if isinstance(doc, list): return [serialize_doc(d) for d in doc]
    if '_id' in doc: doc['_id'] = str(doc['_id'])
    if 'user_id' in doc and isinstance(doc['user_id'], ObjectId): doc['user_id'] = str(doc['user_id'])
    for k, v in doc.items():
        if isinstance(v, ObjectId): doc[k] = str(v)
    return doc

# ==================================================
#           AI ENGINE (STABLE 1.5)
# ==================================================
def generate_immediate_reply(msg, media_bytes=None, media_mime=None, is_void=False, context_memories=[]):
    """
    Generates chat response using the STABLE Gemini 1.5 Flash model.
    """
    try:
        # Construct Context
        memory_block = ""
        if context_memories:
            memory_block = "\n\nRELEVANT PAST:\n" + "\n".join([f"- {m['date']}: {m['full_message']}" for m in context_memories])

        role = "You are 'The Void'. Absorb pain. Be silent." if is_void else "You are Celi. A warm, adaptive AI companion. Keep responses short (max 2-3 sentences) and human-like."
        system_instruction = role + memory_block

        content = [msg]
        if media_bytes and media_mime:
            content.append({'mime_type': media_mime, 'data': media_bytes})

        # MODEL SELECTION: 1.5 Flash is the current stable standard.
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
        
        response = model.generate_content(content)
        return response.text.strip()

    except Exception as e:
        print(f"❌ AI GENERATION ERROR: {e}")
        return "I'm listening, but my connection to the stars is a bit faint right now. I've saved your entry."

def find_similar_memories_sync(user_id, query_text):
    if not query_text or db.history_col is None: return []
    try:
        result = genai.embed_content(model="models/text-embedding-004", content=query_text)
        query_vector = result['embedding']
        pipeline = [
            {"$vectorSearch": {
                "index": "vector_index", "path": "embedding", "queryVector": query_vector,
                "numCandidates": 50, "limit": 2, "filter": {"user_id": user_id}
            }},
            {"$project": {"_id": 0, "full_message": 1, "date": 1, "score": {"$meta": "vectorSearchScore"}}}
        ]
        return list(db.history_col.aggregate(pipeline))
    except: return []

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
    username, password = request.form.get('username'), request.form.get('password')
    user = db.users_col.find_one({"username": username})
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['user_id']
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "error": "Invalid Credentials"}), 401

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

        # Media Handling
        media_id, audio_id, image_bytes = None, None, None
        if image_file and db.fs:
            media_id = db.fs.put(image_file.read(), filename=f"img_{timestamp}", content_type=image_file.mimetype)
            image_bytes = db.fs.get(media_id).read()
        if audio_file and db.fs:
            audio_id = db.fs.put(audio_file, filename=f"aud_{timestamp}", content_type=audio_file.mimetype)

        # AI Processing
        past_memories = find_similar_memories_sync(session['user_id'], msg) if len(msg) > 10 else []
        reward_result = process_daily_rewards(db.users_col, session['user_id'], msg)
        
        reply = generate_immediate_reply(
            msg, image_bytes, image_file.mimetype if image_file else None, 
            (mode == 'rant'), past_memories
        )

        # Database Save
        db.history_col.insert_one({
            "user_id": session['user_id'], "timestamp": timestamp, "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": "Processing...", "full_message": msg, "reply": reply, "ai_analysis": None, "mode": mode,
            "has_media": bool(media_id), "media_file_id": media_id, "has_audio": bool(audio_id), "audio_file_id": audio_id,
            "constellation_name": None, "is_valid_star": reward_result['awarded'], "embedding": None
        })

        # Background Tasks
        try:
            process_entry_analysis.delay(timestamp, msg, session['user_id'])
            generate_weekly_insight.delay(session['user_id'])
        except: pass

        # Reward Check
        command, system_msg = None, ""
        if update_rank_check(db.users_col, session['user_id']) == "level_up":
            command, system_msg = "level_up", f"\n\n[System]: Level Up! {reward_result.get('message', '')}"
        elif reward_result['awarded']:
            command, system_msg = "daily_reward", f"\n\n[System]: {reward_result['message']}"

        return jsonify({"reply": reply + system_msg, "command": command})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": "Signal Lost. Please try again."}), 500

@app.route('/api/data')
def get_data():
    if 'user_id' not in session: return jsonify({"status": "guest"}), 401
    
    # 1. Fetch User (Fast)
    user = db.users_col.find_one({"user_id": session['user_id']})
    if not user: return jsonify({"status": "error"}), 404
    user = serialize_doc(user)

    # 2. Calc Rank
    rank_info = get_rank_meta(user.get('rank_index', 0))
    progression_tree = get_all_ranks_data()
    max_dust = rank_info['req']
    current_dust = user.get('stardust', 0)

    # 3. HISTORY OPTIMIZATION
    history_cursor = db.history_col.find(
        {"user_id": session['user_id']}, 
        {"full_message": 0, "ai_analysis": 0, "embedding": 0}
    ).sort("timestamp", 1)
    
    loaded_history = {doc['timestamp']: serialize_doc(doc) for doc in history_cursor}

    # 4. Trivia Check
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_trivia = user.get("daily_trivia", {})
    if current_trivia.get("date") != today_str:
        try:
            generate_daily_trivia_task.delay(session['user_id'])
            daily_trivia = {"fact": "Scouring the universe...", "loading": True}
        except: daily_trivia = {"fact": "Archive offline.", "loading": False}
    else:
        daily_trivia = current_trivia

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
        "progression_tree": progression_tree,
        "weekly_insight": user.get("weekly_insight", None),
        "daily_trivia": daily_trivia
    })

# --- SUPPORTING ROUTES ---
@app.route('/api/galaxy_map')
def galaxy_map():
    if 'user_id' not in session: return jsonify([])
    cursor = db.history_col.find({"user_id": session['user_id']}, {'_id': 0, 'full_message': 0, 'reply': 0, 'embedding': 0}).sort("timestamp", 1)
    stars = [serialize_doc(doc) for doc in cursor]
    return jsonify([{**doc, "id": doc['timestamp'], "group": i//7, "type": "void" if doc.get('mode')=='rant' else "journal"} for i, doc in enumerate(stars)])

@app.route('/api/star_detail', methods=['POST'])
def star_detail():
    if 'user_id' not in session: return jsonify({"error": "Auth"})
    entry = db.history_col.find_one({"user_id": session['user_id'], "timestamp": request.json.get('id')}, {'embedding': 0})
    if not entry: return jsonify({"error": "Not found"})
    entry = serialize_doc(entry)
    return jsonify({
        "date": entry['date'], "analysis": entry.get('ai_analysis', "Generating..."), "summary": entry.get('summary', '...'),
        "image_url": f"/api/media/{entry['media_file_id']}" if entry.get('media_file_id') else None,
        "audio_url": f"/api/media/{entry['audio_file_id']}" if entry.get('audio_file_id') else None,
        "mode": entry.get('mode', 'journal')
    })

@app.route('/api/media/<file_id>')
def get_media(file_id):
    try:
        grid_out = db.fs.get(ObjectId(file_id))
        return Response(grid_out.read(), mimetype=grid_out.content_type)
    except: return "File not found", 404

@app.route('/api/update_pfp', methods=['POST'])
def update_pfp():
    try:
        file_id = db.fs.put(request.files['pfp'].read(), filename=f"pfp_{session['user_id']}", content_type=request.files['pfp'].mimetype)
        db.users_col.update_one({"user_id": session['user_id']}, {"$set": {"profile_pic": f"/api/media/{file_id}"}})
        return jsonify({"status": "success", "url": f"/api/media/{file_id}"})
    except: return jsonify({"status": "error"})

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        if db.users_col.find_one({"username": data['reg_username']}): return jsonify({"status": "error", "error": "Username taken"})
        db.users_col.insert_one({
            "user_id": str(uuid.uuid4()), "username": data['reg_username'], "password_hash": generate_password_hash(data['reg_password']),
            "first_name": data['fname'], "last_name": data['lname'], "dob": data['dob'], "aura_color": data.get('fav_color', '#00f2fe'),
            "secret_question": data['secret_question'], "secret_answer_hash": generate_password_hash(data['secret_answer'].lower().strip()),
            "rank": "Observer III", "rank_index": 0, "stardust": 0, "profile_pic": "", "joined_at": datetime.now()
        })
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "error": str(e)})

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    db.users_col.update_one({"user_id": session['user_id']}, {"$set": {k:v for k,v in request.json.items() if k in ['first_name','last_name','aura_color']}})
    return jsonify({"status": "success"})

@app.route('/api/update_security', methods=['POST'])
def update_security():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    updates = {}
    if 'new_password' in request.json: updates['password_hash'] = generate_password_hash(request.json['new_password'])
    if 'new_secret_a' in request.json: 
        updates['secret_question'] = request.json['new_secret_q']
        updates['secret_answer_hash'] = generate_password_hash(request.json['new_secret_a'].lower().strip())
    db.users_col.update_one({"user_id": session['user_id']}, {"$set": updates})
    return jsonify({"status": "success"})

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    db.history_col.delete_many({"user_id": session['user_id']})
    db.users_col.delete_one({"user_id": session['user_id']})
    session.clear()
    return jsonify({"status": "success"})

@app.route('/privacy_policy')
def privacy_policy(): return render_template('privacy_policy.html')
@app.route('/sw.js')
def service_worker(): return send_from_directory('static', 'sw.js', mimetype='application/javascript')
@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json', mimetype='application/json')

if __name__ == '__main__': app.run(debug=True, port=5000)
