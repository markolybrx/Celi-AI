import os
import logging
import traceback
import certifi
import uuid
import redis
import ssl
import json
import gridfs
import random
from bson.objectid import ObjectId
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, Response
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import google.generativeai as genai
from pymongo import MongoClient

# --- ENV LOADER (NEW) ---
from dotenv import load_dotenv
load_dotenv() # <--- This loads your .env file locally

# --- IMPORT RANK LOGIC ---
try:
    from rank_system import process_daily_rewards, update_rank_check, get_rank_meta, get_all_ranks_data, RANK_SYSTEM
except ImportError:
    # Fallback to prevent crash if file missing during setup
    RANK_SYSTEM = []
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
app.config['PERMANENT_SESSION_LIFETIME'] = 3600 * 24 * 7 # 7 Days

# Redis Connection (Handle both Local and Production URL)
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
if redis_url.startswith('rediss://'):
    # Production (Render/Vercel) often needs SSL certs ignored for Redis
    app.config['SESSION_REDIS'] = redis.from_url(redis_url, ssl_cert_reqs=None)
else:
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)

Session(app)

# --- CONFIG: MONGODB ---
MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI:
    logging.warning("MONGO_URI not found. App will crash on DB access.")

try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['celi_db']
    users_col = db['users']
    history_col = db['history']
    fs = gridfs.GridFS(db)
    logging.info("Connected to MongoDB Atlas.")
except Exception as e:
    logging.error(f"MongoDB Connection Failed: {e}")

# --- CONFIG: GEMINI AI ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # Use the Flash model for speed
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    logging.warning("GEMINI_API_KEY not set.")

# ==================================================
#                 CORE ROUTES
# ==================================================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('auth.html')

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==================================================
#                 API: AUTH
# ==================================================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    # Secret Question for recovery
    sq_id = data.get('secret_q_id')
    sq_ans = data.get('secret_ans')

    if users_col.find_one({"username": username}):
        return jsonify({"status": "error", "message": "Username taken"}), 400

    hashed = generate_password_hash(password)
    
    uid = str(uuid.uuid4())
    new_user = {
        "user_id": uid,
        "username": username,
        "password": hashed,
        "secret_q_id": sq_id,
        "secret_ans": sq_ans.lower().strip() if sq_ans else "",
        "created_at": datetime.now(timezone.utc),
        "stardust": 0,
        "rank_index": 0,
        "rank": "Observer",
        "xp": 0
    }
    users_col.insert_one(new_user)
    session['user_id'] = uid
    return jsonify({"status": "success", "redirect": "/"})

@app.route('/api/login_check', methods=['POST'])
def login_check():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = users_col.find_one({"username": username})
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['user_id']
        
        # --- SYNCHRONOUS DAILY REWARD CHECK ---
        process_daily_rewards(user['user_id'], db)
        
        return jsonify({"status": "success", "redirect": "/"})
    
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/api/get_security_q', methods=['POST'])
def get_security_q():
    """Fetch user's security question ID for recovery"""
    data = request.json
    username = data.get('username')
    user = users_col.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    return jsonify({"status": "success", "q_id": user.get('secret_q_id', 'mother_maiden')})

@app.route('/api/recover', methods=['POST'])
def recover_account():
    data = request.json
    username = data.get('username')
    ans = data.get('secret_answer', '').lower().strip()
    
    user = users_col.find_one({"username": username})
    if user and user.get('secret_ans') == ans:
        return jsonify({"status": "success", "username": username})
    return jsonify({"status": "error"}), 401

@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    username = data.get('username')
    new_pw = data.get('new_password')
    
    hashed = generate_password_hash(new_pw)
    users_col.update_one({"username": username}, {"$set": {"password": hashed}})
    return jsonify({"status": "success"})

# ==================================================
#                 API: DATA & RANK
# ==================================================

@app.route('/api/get_user_data')
def get_user_data():
    if 'user_id' not in session: return jsonify({}), 401
    user = users_col.find_one({"user_id": session['user_id']}, {"_id": 0, "password": 0, "secret_ans": 0})
    
    # Enrich with Rank Meta
    rank_title = user.get('rank', 'Observer')
    # Identify index based on title
    r_idx = 0
    for i, r in enumerate(RANK_SYSTEM):
        if r['title'] == rank_title:
            r_idx = i
            break
            
    # Get Next Level Meta
    current_req = RANK_SYSTEM[r_idx]['req']
    next_req = RANK_SYSTEM[r_idx+1]['req'] if r_idx + 1 < len(RANK_SYSTEM) else current_req
    
    psyche_type = RANK_SYSTEM[r_idx]['psyche']
    
    user['rank_index'] = r_idx
    user['star_type'] = psyche_type
    user['next_level_xp'] = next_req
    
    # Get PFP URL
    if 'profile_pic_id' in user:
        user['pfp_url'] = f"/api/media/{user['profile_pic_id']}"
    
    return jsonify(user)

@app.route('/api/ranks_tree')
def get_ranks_tree():
    """Returns the static rank definition for the modal tree"""
    return jsonify(get_all_ranks_data())

# ==================================================
#                 API: CHAT & AI
# ==================================================

@app.route('/api/process', methods=['POST'])
def process_chat():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    uid = session['user_id']
    data = request.json
    user_msg = data.get('message', '')
    mode = data.get('mode', 'journal') # 'journal' (Celi) or 'rant' (Void)
    
    # 1. Store User Message
    entry_id = history_col.insert_one({
        "user_id": uid,
        "role": "user",
        "content": user_msg,
        "mode": mode,
        "date": datetime.now(timezone.utc),
        "type": "text"
    }).inserted_id
    
    # 2. Generate AI Response
    system_instruction = ""
    if mode == 'rant':
        # VOID MODE: Minimalist, absorbing, validates pain
        system_instruction = "You are The Void. You are a listener. Absorb the user's negativity. Be brief, stoic, but acknowledging. Do not offer solutions. Just hear them. Use lower case mostly."
    else:
        # CELI MODE: Analytical, Mirror Protocol, High-Level
        system_instruction = "You are Celi, a sovereign AI mirror. Your goal is to reflect the user's psyche back to them. Be insightful, slightly cryptic but warm. Analyze their patterns. Use brief, punchy sentences. Do not sound like a generic assistant."

    try:
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_instruction]}
        ])
        response = chat.send_message(user_msg)
        ai_text = response.text
    except Exception as e:
        ai_text = "I am having trouble connecting to the stars right now..."
        logging.error(f"Gemini Error: {e}")

    # 3. Store AI Response
    history_col.insert_one({
        "user_id": uid,
        "role": "model",
        "content": ai_text,
        "mode": mode,
        "date": datetime.now(timezone.utc),
        "type": "text"
    })
    
    # 4. Update Rank / XP (Synchronous)
    users_col.update_one({"user_id": uid}, {"$inc": {"stardust": 10, "xp": 10}})
    new_rank, msg = update_rank_check(uid, users_col, history_col)
    
    return jsonify({
        "response": ai_text, 
        "rank_up": new_rank,
        "rank_msg": msg
    })

# ==================================================
#                 API: GALAXY & HISTORY
# ==================================================

@app.route('/api/get_history')
def get_history():
    if 'user_id' not in session: return jsonify([])
    # Get last 30 entries for the list view
    entries = list(history_col.find({"user_id": session['user_id'], "role": "user"}).sort("date", -1).limit(30))
    for e in entries:
        e['_id'] = str(e['_id'])
        e['date'] = e['date'].isoformat()
    return jsonify(entries)

@app.route('/api/galaxy_map')
def get_galaxy_map():
    if 'user_id' not in session: return jsonify([])
    
    cursor = history_col.find(
        {"user_id": session['user_id'], "role": "user"},
        {"content": 1, "mode": 1, "date": 1}
    ).sort("date", -1)
    
    stars = []
    for doc in cursor:
        color = "#00f2fe" # Default Celi Blue
        if doc.get('mode') == 'rant':
            color = "#ef4444" # Void Red
            
        stars.append({
            "id": str(doc['_id']),
            "date": doc['date'].isoformat(),
            "preview": doc['content'][:50] + "...",
            "type": doc.get('mode', 'journal'),
            "color": color
        })
        
    return jsonify(stars)

@app.route('/api/star_detail')
def get_star_detail():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    entry_id = request.args.get('id')
    if not entry_id: return jsonify({"error": "No ID"}), 400
    
    try:
        entry = history_col.find_one({"_id": ObjectId(entry_id), "user_id": session['user_id']})
        if not entry: return jsonify({"error": "Not Found"}), 404
        
        ai_reply = history_col.find_one({
            "user_id": session['user_id'],
            "role": "model",
            "date": {"$gt": entry['date']}
        }, sort=[("date", 1)])
        
        analysis_text = ai_reply['content'] if ai_reply else "No analysis found for this memory."
        
        return jsonify({
            "date": entry['date'].strftime("%B %d, %Y"),
            "content": entry['content'],
            "analysis": analysis_text,
            "image_id": entry.get('image_id'),
            "audio_id": entry.get('audio_id')
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================
#                 API: MEDIA (GridFS)
# ==================================================

@app.route('/api/media/<file_id>')
def get_media(file_id):
    try:
        grid_out = fs.get(ObjectId(file_id))
        return Response(grid_out.read(), mimetype=grid_out.content_type)
    except:
        return "File not found", 404

# ==================================================
#                 MAIN EXECUTION
# ==================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)