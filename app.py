import os
import logging
import traceback
import uuid
import json
import time
from datetime import datetime
from bson.objectid import ObjectId
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, Response
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash

# --- SAFE IMPORTS ---
try:
    import requests
except ImportError:
    requests = None
    print("⚠️ WARNING: 'requests' library not found. HTTP Fallback disabled.")

try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("⚠️ WARNING: 'google.generativeai' library not found. AI disabled.")

# --- DATABASE IMPORT WITH SAFETY CHECK ---
try:
    import database as db
    if db.users_col is None:
        print("❌ CRITICAL: Database collections are None. Check DB Connection.")
except Exception as e:
    print(f"❌ CRITICAL: Database import failed: {e}")
    db = None

# --- TASKS IMPORT ---
process_entry_analysis = None
generate_constellation_name_task = None
generate_weekly_insight = None
generate_daily_trivia_task = None

try:
    from tasks import (
        process_entry_analysis, 
        generate_constellation_name_task, 
        generate_weekly_insight, 
        generate_daily_trivia_task
    )
except ImportError:
    print("⚠️ Warning: Tasks module failed to load.")
except Exception as e:
    print(f"⚠️ Warning: Error importing tasks: {e}")

from rank_system import process_daily_rewards, update_rank_check, get_rank_meta, get_all_ranks_data

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'celi_fallback_key_12345')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# --- SAFE SESSION INIT ---
# If Redis fails, we fall back to filesystem or cookie to prevent 500 Error
if db and db.redis_client:
    app.config['SESSION_REDIS'] = db.redis_client
    try:
        server_session = Session(app)
    except Exception as e:
        print(f"⚠️ Redis Session Failed: {e}. Falling back to default.")
        app.config['SESSION_TYPE'] = 'filesystem'
        Session(app)
else:
    print("⚠️ No Redis Client. Using filesystem session.")
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)

# --- AI CONFIG ---
api_key = os.environ.get("GEMINI_API_KEY")
clean_key = ""
CACHED_MODEL_NAME = None

if api_key and genai:
    clean_key = api_key.strip().replace("'", "").replace('"', "").replace("\n", "").replace("\r", "")
    try:
        genai.configure(api_key=clean_key)
        print(f"✅ AI Core Online.")
    except Exception as e:
        print(f"❌ AI Config Failed: {e}")

def serialize_doc(doc):
    if not doc: return None
    if isinstance(doc, list): return [serialize_doc(d) for d in doc]
    if '_id' in doc: doc['_id'] = str(doc['_id'])
    if 'user_id' in doc and isinstance(doc['user_id'], ObjectId): doc['user_id'] = str(doc['user_id'])
    for k, v in doc.items():
        if isinstance(v, ObjectId): doc[k] = str(v)
    return doc

# ==================================================
#           ROBUST AI ENGINE
# ==================================================
def get_valid_model_name():
    global CACHED_MODEL_NAME
    if CACHED_MODEL_NAME: return CACHED_MODEL_NAME
    if not requests: return "gemini-pro"

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if "error" in data: return None

        preferred_order = ["gemini-2.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        available_models = [m['name'].replace("models/", "") for m in data.get('models', []) if 'generateContent' in m['supportedGenerationMethods']]
        
        for pref in preferred_order:
            if pref in available_models:
                CACHED_MODEL_NAME = pref
                return pref
        
        if available_models:
            CACHED_MODEL_NAME = available_models[0]
            return available_models[0]
            
        return None
    except: return "gemini-pro"

def generate_immediate_reply(msg, media_bytes=None, media_mime=None, is_void=False, context_memories=[]):
    if not clean_key: return "Configuration Error: API Key missing."
    
    model_name = get_valid_model_name() or "gemini-pro"

    memory_block = ""
    if context_memories:
        memory_block = "\n\nRELEVANT PAST:\n" + "\n".join([f"- {m['date']}: {m['full_message']}" for m in context_memories])

    role = "You are 'The Void'. Absorb pain. Be silent." if is_void else "You are Celi. A warm, adaptive AI companion. Keep responses short (max 2-3 sentences) and human-like."
    system_instruction = role + memory_block
    full_prompt = f"{system_instruction}\n\nUser: {msg}"

    if requests:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
            payload = { "contents": [{ "parts": [{"text": full_prompt}] }] }
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            data = response.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except: pass
    
    return "I'm listening, but the connection is faint."

def find_similar_memories_sync(user_id, query_text):
    return []

# ==================================================
#                 ROUTES (CRASH PROOF)
# ==================================================

@app.route('/')
def index():
    try:
        if 'user_id' not in session: return redirect(url_for('login_page'))
        return render_template('index.html')
    except Exception as e:
        traceback.print_exc()
        return f"CRITICAL ERROR IN INDEX: {e}", 500

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    try:
        if request.method == 'GET': 
            return redirect(url_for('index')) if 'user_id' in session else render_template('auth.html')
        
        # POST LOGIC
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 1. DB Safety Check
        if db is None or db.users_col is None:
            return jsonify({"status": "error", "error": "Database Disconnected"}), 500

        user = db.users_col.find_one({"username": username})
        
        if user and check_password_hash(user['password_hash'], password):
            try:
                session['user_id'] = user['user_id']
                return jsonify({"status": "success"})
            except Exception as se:
                print(f"❌ Session Write Failed: {se}")
                return jsonify({"status": "error", "error": "Session/Redis Failure"}), 500
        else:
            return jsonify({"status": "error", "error": "Invalid Credentials"}), 401

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": f"Login Crash: {str(e)}"}), 500

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

        media_id, audio_id = None, None
        if image_file and db.fs:
            media_id = db.fs.put(image_file.read(), filename=f"img_{timestamp}", content_type=image_file.mimetype)
        if audio_file and db.fs:
            audio_id = db.fs.put(audio_file, filename=f"aud_{timestamp}", content_type=audio_file.mimetype)

        reward_result = process_daily_rewards(db.users_col, session['user_id'], msg)
        reply = generate_immediate_reply(msg, None, None, (mode == 'rant'), [])
        
        instant_summary = (msg[:60] + "...") if len(msg) > 60 else msg

        db.history_col.insert_one({
            "user_id": session['user_id'], "timestamp": timestamp, "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": instant_summary, "full_message": msg, "reply": reply, "ai_analysis": None, "mode": mode,
            "has_media": bool(media_id), "media_file_id": media_id, "has_audio": bool(audio_id), "audio_file_id": audio_id,
            "constellation_name": None, "is_valid_star": reward_result['awarded'], "embedding": None
        })

        if process_entry_analysis:
            try: process_entry_analysis.delay(timestamp, msg, session['user_id'])
            except: pass
        if generate_weekly_insight:
            try: generate_weekly_insight.delay(session['user_id'])
            except: pass

        command, system_msg = None, ""
        if update_rank_check(db.users_col, session['user_id']) == "level_up":
            command, system_msg = "level_up", f"\n\n[System]: Level Up! {reward_result.get('message', '')}"
        elif reward_result['awarded']:
            command, system_msg = "daily_reward", f"\n\n[System]: {reward_result['message']}"

        return jsonify({"reply": reply + system_msg, "command": command})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"Signal Lost: {str(e)}"}), 500

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

    history_cursor = db.history_col.find({"user_id": session['user_id']}, {"full_message": 0, "ai_analysis": 0, "embedding": 0}).sort("timestamp", 1)
    loaded_history = {doc['timestamp']: serialize_doc(doc) for doc in history_cursor}

    today_str = datetime.now().strftime("%Y-%m-%d")
    current_trivia = user.get("daily_trivia", {})
    
    if current_trivia.get("date") != today_str:
        if generate_daily_trivia_task: 
            try:
                generate_daily_trivia_task.delay(session['user_id'])
                daily_trivia = {"fact": "Scouring the universe...", "loading": True}
            except: 
                daily_trivia = {"fact": "Archive offline (Task Error).", "loading": False}
        else:
            daily_trivia = {"fact": "Archive offline (Import Error).", "loading": False}
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