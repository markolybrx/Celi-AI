import os
import json
import random
import requests
from celery import Celery
import google.generativeai as genai
from datetime import datetime
import database as db

# --- SETUP CELERY ---
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
celery_app = Celery('tasks', broker=redis_url, backend=redis_url)

# --- AI CONFIG ---
api_key = os.environ.get("GEMINI_API_KEY")
clean_key = ""
if api_key:
    clean_key = api_key.strip().replace("'", "").replace('"', "")
    genai.configure(api_key=clean_key)

# --- HELPER: MODEL DISCOVERY (COPIED FROM APP.PY) ---
def get_working_model():
    """
    Finds the first available model for this specific API key.
    """
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
        response = requests.get(url)
        data = response.json()
        
        preferred_order = ["gemini-2.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        available_models = [m['name'].replace("models/", "") for m in data.get('models', []) if 'generateContent' in m['supportedGenerationMethods']]
        
        for pref in preferred_order:
            if pref in available_models: return pref
        
        return available_models[0] if available_models else "gemini-pro"
    except:
        return "gemini-pro"

@celery_app.task
def process_entry_analysis(timestamp, message, user_id):
    try:
        model_name = get_working_model()
        model = genai.GenerativeModel(model_name)
        prompt = f"""
        Analyze this journal entry psychologically.
        Entry: "{message}"
        
        Return a JSON object with:
        - "mood": (String) The dominant emotion.
        - "keywords": (List) 3 key themes.
        - "short_summary": (String) A 10-word summary.
        """
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        analysis_data = json.loads(clean_text)
        
        db.history_col.update_one(
            {"user_id": user_id, "timestamp": timestamp},
            {"$set": {
                "ai_analysis": analysis_data,
                "summary": analysis_data.get('short_summary', 'Entry processed.')
            }}
        )
    except Exception as e:
        print(f"❌ Analysis Failed: {e}")

@celery_app.task
def generate_weekly_insight(user_id):
    try:
        cursor = db.history_col.find({"user_id": user_id}, {"full_message": 1, "date": 1}).sort("timestamp", -1).limit(7)
        entries = list(cursor)
        if not entries: return

        text_block = "\n".join([f"[{e['date']}]: {e.get('full_message','')}" for e in entries])
        
        model_name = get_working_model()
        model = genai.GenerativeModel(model_name)
        prompt = f"""
        Act as Celi, a psychological AI advisor.
        Analyze these journal entries from the last 7 days.
        Return a JSON object: {{"observation": "One sentence observation.", "advice": "One sentence advice."}}
        Entries: {text_block}
        """
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_text)
        
        updates = { "weekly_insight": { "status": "active", "text": data.get('observation', "Analyzing stars..."), "recommendation": data.get('advice', "Keep writing.") } }
        db.users_col.update_one({"user_id": user_id}, {"$set": updates})
    except Exception as e:
        print(f"❌ Insight Failed: {e}")

@celery_app.task
def generate_daily_trivia_task(user_id):
    """
    Generates unique cosmic trivia.
    """
    try:
        topics = ["black holes", "neutron stars", "dark matter", "exoplanets", "constellation mythology", "the big bang", "quasars", "nebulae", "time dilation", "the solar system"]
        topic = random.choice(topics)
        
        model_name = get_working_model()
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""
        Tell me a unique, mind-blowing trivia fact about {topic} in the context of Astronomy or Cosmology.
        It must be different from common facts.
        Keep it under 25 words.
        Return ONLY the fact text.
        """
        
        response = model.generate_content(prompt)
        fact_text = response.text.strip()
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        db.users_col.update_one(
            {"user_id": user_id},
            {"$set": {
                "daily_trivia": {
                    "date": today_str,
                    "fact": fact_text,
                    "topic": topic,
                    "loading": False
                }
            }}
        )
        print(f"✅ Trivia Generated: {fact_text}")

    except Exception as e:
        print(f"❌ Trivia Failed: {e}")
        # Fallback only on total failure
        db.users_col.update_one(
            {"user_id": user_id},
            {"$set": {"daily_trivia": {"date": "error", "fact": "The archive is reorganizing star charts. Check back later.", "loading": False}}}
        )

# Legacy
@celery_app.task
def generate_constellation_name_task(user_id, timestamp, text_block): pass 