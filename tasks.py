import os
import google.generativeai as genai
from celery import Celery
import database as db  # Import our shared DB connection

# --- CONFIG: CELERY ---
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
if 'redis://' in redis_url and ('upstash' in redis_url or 'rediss' in redis_url):
     redis_url = redis_url.replace('redis://', 'rediss://', 1)

# Initialize Celery
celery_app = Celery('celi_worker', broker=redis_url, backend=redis_url)

# --- CONFIG: AI ---
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    clean_key = api_key.strip().replace("'", "").replace('"', "")
    genai.configure(api_key=clean_key)

# ==================================================
#                ASYNC TASKS
# ==================================================

@celery_app.task
def process_entry_analysis(entry_id, text, user_id):
    """
    Background Task:
    1. Generates Embeddings (Vector)
    2. Generates Psychological Analysis
    3. Generates Summary
    4. Checks Constellation Names
    """
    print(f"⚙️ [Worker] Processing Entry: {entry_id}")
    
    updates = {}
    
    # 1. Generate Embedding
    try:
        if len(text) > 5:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document",
                title="Journal Entry"
            )
            updates['embedding'] = result['embedding']
    except Exception as e:
        print(f"⚠️ Embedding Failed: {e}")

    # 2. Generate Analysis
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"Provide a warm, human-like psychological insight about this journal entry. Speak directly to 'You'. Keep it to 1 or 2 sentences max. Entry: {text}"
        res = model.generate_content(prompt)
        updates['ai_analysis'] = res.text.strip()
    except Exception as e:
        print(f"⚠️ Analysis Failed: {e}")

    # 3. Generate Summary
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"Write a 1 or 2 sentence recap of this entry addressed to 'You', as if you are a supportive friend remembering it. Do not start with 'You mentioned'. Entry: {text}"
        res = model.generate_content(prompt)
        updates['summary'] = res.text.strip().replace('"', '').replace("'", "")
    except Exception as e:
        updates['summary'] = text[:50] + "..."

    # 4. Constellation Name Check
    # (We fetch the last 7 entries to see if a group was formed)
    try:
        # Note: We rely on the app to tell us if a constellation logic was triggered, 
        # but here we can just generate a name if we want to update the latest entry.
        pass 
    except:
        pass

    # 5. COMMIT UPDATES TO DB
    if updates:
        db.history_col.update_one(
            {"user_id": user_id, "timestamp": entry_id},
            {"$set": updates}
        )
        print(f"✅ [Worker] Entry {entry_id} Updated successfully.")

@celery_app.task
def generate_constellation_name_task(user_id, entry_id, text_block):
    """Generates a name for a completed constellation."""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"Here are 7 days of journal entries. Give them a mystical 'Constellation Name' (e.g., 'The Week of Rain'). Just the name. Entries: {text_block}"
        response = model.generate_content(prompt)
        name = response.text.strip().replace('"', '').replace("'", "")
        
        db.history_col.update_one(
            {"user_id": user_id, "timestamp": entry_id},
            {"$set": {"constellation_name": name}}
        )
    except Exception as e:
        print(f"⚠️ Constellation Name Failed: {e}")

@celery_app.task
def generate_weekly_insight(user_id):
    """
    Analyzes the last 7 days of entries to provide a pattern + advice.
    """
    try:
        # 1. Fetch last 7 days of history
        cursor = db.history_col.find(
            {"user_id": user_id}, 
            {"full_message": 1, "date": 1, "mode": 1}
        ).sort("timestamp", -1).limit(7)
        
        entries = list(cursor)
        
        updates = {}

        # 2. Logic: Empty Sky vs. Active Orbit
        if not entries:
            # STATE A: Persuasion (Hardcoded to save API costs)
            updates['weekly_insight'] = {
                "status": "empty",
                "text": "The galaxy is quiet. I cannot navigate your stars if they do not exist. Share one small moment from today?",
                "recommendation": "Start small. Just write one sentence."
            }
        else:
            # STATE B: Active Analysis (Gemini)
            text_block = "\n".join([f"[{e['date']}]: {e.get('full_message','')}" for e in entries])
            
            model = genai.GenerativeModel("gemini-2.5-flash")
            prompt = f"""
            Act as Celi, a warm, psychological AI companion.
            Analyze these user journal entries from the last 7 days.
            
            Return a valid JSON object (no markdown formatting) with exactly two fields:
            1. "observation": A 1-sentence observation about their mood patterns or recurring themes.
            2. "advice": A 1-sentence specific, actionable micro-strategy or concept (e.g., 'Try the Pomodoro technique', 'Focus on sleep hygiene'). Do not recommend specific URLs.
            
            Entries:
            {text_block}
            """
            
            try:
                result = model.generate_content(prompt)
                # Clean the response to ensure it's pure JSON
                clean_json = result.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean_json)
                
                updates['weekly_insight'] = {
                    "status": "active",
                    "text": data.get('observation', "I'm analyzing your new patterns."),
                    "recommendation": data.get('advice', "Keep writing to reveal more stars.")
                }
            except:
                # Fallback if AI JSON fails
                updates['weekly_insight'] = {
                    "status": "active",
                    "text": "I sense complex emotions in your recent entries.",
                    "recommendation": "Take a moment to breathe deeply before your next task."
                }

        # 3. Save to User Profile (so it loads fast on dashboard)
        db.users_col.update_one({"user_id": user_id}, {"$set": updates})
        print(f"✅ [Worker] Insight generated for {user_id}")

    except Exception as e:
        print(f"⚠️ Insight Generation Failed: {e}")

@celery_app.task
def generate_daily_trivia_task(user_id):
    """
    Asks Gemini for a unique daily fact for the user.
    Stores it with today's date so it doesn't regenerate until tomorrow.
    """
    try:
        import random
        topics = ["astronomy", "psychology", "nature", "ancient history", "quantum physics", "philosophy", "neuroscience"]
        topic = random.choice(topics)
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""
        Tell me a fascinating, lesser-known fact about {topic}. 
        It should be short (minimum 20 words but not more than 40 words), awe-inspiring, and sound like something a smart friend would share.
        Return ONLY the fact as plain text. No 'Here is a fact:' prefix.
        """
        
        response = model.generate_content(prompt)
        fact_text = response.text.strip()
        
        # Save to user profile with today's date
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        db.users_col.update_one(
            {"user_id": user_id},
            {"$set": {
                "daily_trivia": {
                    "date": today_str,
                    "fact": fact_text,
                    "topic": topic
                }
            }}
        )
        print(f"✅ [Worker] Trivia generated for {user_id}")
    except Exception as e:
        print(f"⚠️ Trivia Generation Failed: {e}")