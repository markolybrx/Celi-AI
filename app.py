import os
import logging
import uuid
import json
import requests
from bson.objectid import ObjectId
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, Response
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import google.generativeai as genai
import database as db

# --- SETUP APP ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'celi_key')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = db.redis_client 
server_session = Session(app)

# --- AI CONFIGURATION ---
api_key = os.environ.get("GEMINI_API_KEY")
clean_key = ""
CACHED_MODEL_NAME = None

if api_key:
    clean_key = api_key.strip().replace("'", "").replace('"', "").replace("\n", "").replace("\r", "")
    genai.configure(api_key=clean_key)

# --- TASKS IMPORT ---
# We use a simple try/except here just to prevent a total crash if Redis is slow
try:
    from tasks import process_entry_analysis, generate_weekly_insight, generate_daily_trivia_task
except ImportError:
    process_entry_analysis = None
    print("⚠️ Background tasks disabled.")

from rank_system import process_daily_rewards, update_rank_check, get_rank_meta, get_all_ranks_data

# --- HELPER ---
def serialize_doc(doc):
    if not doc: return None
    if isinstance(doc, list): return [serialize_doc(d) for d in doc]
    if '_id' in doc: doc['_id'] = str(doc['_id'])
    if 'user_id' in doc: doc['_id'] = str(doc['_id']) 
    for k, v in doc.items():
        if isinstance(v, ObjectId): doc[k] = str(v)
    return doc

# --- AI ENGINE (The ONE thing we keep: Auto-Discovery) ---
def get_valid_model_name():
    global CACHED_MODEL_NAME
    if CACHED_MODEL_NAME: return CACHED_MODEL_NAME

    try:
        # Ask Google what models are available
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Priority List: 2.5 -> 2.0 -> 1.5 -> Pro
        preferred_order = ["gemini-2.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        available_models = [m['name'].replace("models/", "") for m in data.get('models', []) if 'generateContent' in m['supportedGenerationMethods']]
        
        for pref in preferred_order:
            if pref in available_models:
                CACHED_MODEL_NAME = pref
                print(f"🔹 Celi linked to: {pref}")
                return pref
        
        return "gemini-pro"
    except: return "gemini-pro"

def generate_immediate_reply(msg):
    try:
        model_name = get_valid_model_name()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
        payload = { "contents": [{ "parts": [{"text": f"You are Celi. Reply warmly in 2 sentences. User: {msg}"}] }] }
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=8)
        data = response.json()
        if "candidates" in data: return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"AI Error: {e}")
    return "I'm listening, but the connection is faint."

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET': return redirect(url_for('index')) if 'user_id' in session else render_template('auth.html')
    
    username = request.form.get('username')
    password = request.form.get('password')
    
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
    
    msg = request.form.get('message', '')
    mode = request.form.get('mode', 'journal')
    timestamp = str(datetime.now().timestamp())
    
    # 1. Generate Reply
    reply = generate_immediate_reply(msg)
    
    # 2. Check Rewards
    reward_result = process_daily_rewards(db.users_col, session['user_id'], msg)
    
    # 3. Save to DB
    db.history_col.insert_one({
        "user_id": session['user_id'], "timestamp": timestamp, "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": (msg[:60] + "...") if len(msg) > 60 else msg, 
        "full_message": msg, "reply": reply, "ai_analysis": None, "mode": mode
    })

    # 4. Background Tasks
    if process_entry_analysis: 
        try: process_entry_analysis.delay(timestamp, msg, session['user_id'])
        except: pass
        
    command = "level_up" if update_rank_check(db.users_col, session['user_id']) == "level_up" else None
    return jsonify({"reply": reply, "command": command})

@app.route('/api/data')
def get_data():
    if 'user_id' not in session: return jsonify({"status": "guest"}), 401
    
    user = db.users_col.find_one({"user_id": session['user_id']})
    if not user: return jsonify({"status": "error"}), 404
    user = serialize_doc(user)
    
    rank_info = get_rank_meta(user.get('rank_index', 0))
    progression_tree = get_all_ranks_data()
    max_dust = rank_info['req']
    
    history_cursor = db.history_col.find({"user_id": session['user_id']}, {"full_message": 0, "ai_analysis": 0}).sort("timestamp", 1)
    loaded_history = {doc['timestamp']: serialize_doc(doc) for doc in history_cursor}

    return jsonify({
        "status": "user",
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "rank": user.get("rank", "Observer III"),
        "rank_index": user.get("rank_index", 0),
        "rank_progress": (user.get('stardust', 0)/max_dust)*100 if max_dust>0 else 0,
        "stardust_current": user.get('stardust', 0),
        "stardust_max": max_dust,
        "history": loaded_history, 
        "profile_pic": user.get("profile_pic", ""),
        "progression_tree": progression_tree,
        "weekly_insight": user.get("weekly_insight", None),
        "daily_trivia": user.get("daily_trivia", {"fact": "Loading...", "loading": True})
    })

# --- REQUIRED SUPPORT ROUTES ---
@app.route('/api/galaxy_map')
def galaxy_map(): return jsonify([]) 

@app.route('/api/star_detail', methods=['POST'])
def star_detail():
    entry = db.history_col.find_one({"user_id": session['user_id'], "timestamp": request.json.get('id')})
    return jsonify(serialize_doc(entry)) if entry else jsonify({"error": "Not found"})

@app.route('/api/media/<file_id>')
def get_media(file_id):
    try: return Response(db.fs.get(ObjectId(file_id)).read(), mimetype='image/jpeg')
    except: return "File not found", 404

@app.route('/api/update_pfp', methods=['POST'])
def update_pfp():
    f = request.files['pfp']
    fid = db.fs.put(f.read(), filename=f"pfp_{session['user_id']}", content_type=f.mimetype)
    db.users_col.update_one({"user_id": session['user_id']}, {"$set": {"profile_pic": f"/api/media/{fid}"}})
    return jsonify({"status": "success", "url": f"/api/media/{fid}"})

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    db.users_col.update_one({"user_id": session['user_id']}, {"$set": {k:v for k,v in request.json.items() if k in ['first_name','last_name','aura_color']}})
    return jsonify({"status": "success"})

@app.route('/api/update_security', methods=['POST'])
def update_security():
    db.users_col.update_one({"user_id": session['user_id']}, {"$set": {"password_hash": generate_password_hash(request.json['new_password'])}})
    return jsonify({"status": "success"})

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    db.history_col.delete_many({"user_id": session['user_id']})
    db.users_col.delete_one({"user_id": session['user_id']})
    session.clear()
    return jsonify({"status": "success"})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if db.users_col.find_one({"username": data['reg_username']}): return jsonify({"status": "error", "error": "Username taken"})
    db.users_col.insert_one({
        "user_id": str(uuid.uuid4()), "username": data['reg_username'], "password_hash": generate_password_hash(data['reg_password']),
        "first_name": data['fname'], "rank": "Observer III", "rank_index": 0, "stardust": 0
    })
    return jsonify({"status": "success"})

@app.route('/privacy_policy')
def privacy_policy(): return render_template('components/modals/policy.html')
@app.route('/sw.js')
def service_worker(): return send_from_directory('static', 'sw.js', mimetype='application/javascript')
@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json', mimetype='application/json')

if __name__ == '__main__': app.run(debug=True, port=5000)