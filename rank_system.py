from datetime import datetime, timedelta

# ==================================================
#           ASSET LIBRARY (COLORS & SVGS)
# ==================================================

PHASE_COLORS = {
    "Observer": "#00f2fe", "Moonwalker": "#00f2fe",      # Phase 1: Ice Blue
    "Celestial": "#facc15", "Stellar": "#facc15",        # Phase 2: Solar Gold
    "Interstellar": "#facc15",
    "Galactic": "#a855f7", "Intergalactic": "#a855f7",   # Phase 3: Cosmic Purple
    "Ethereal": "#ffffff"                                # Phase 4: Pure White
}

# Geometric Vector Icons (Solid Cutout Style)
RANK_ICONS = {
    'Observer': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 1C5.9 1 1 5.9 1 12C1 18.1 5.9 23 12 23C18.1 23 23 18.1 23 12C23 5.9 18.1 1 12 1ZM12 18C15.5 18 18.5 15.5 19 12C18.5 8.5 15.5 6 12 6C8.5 6 5.5 8.5 5 12C5.5 15.5 8.5 18 12 18ZM12 15C13.65 15 15 13.65 15 12C15 10.35 13.65 9 12 9C10.35 9 9 10.35 9 12C9 13.65 10.35 15 12 15Z"/></svg>""",
    
    'Moonwalker': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 1L1 22H23L12 1ZM12 18.5C13.6 18.5 15 17.1 15 15.5C15 13.5 13.5 12 12 12C10.5 12 9 13.5 9 15.5C9 17.1 10.4 18.5 12 18.5ZM12 6.5L16 13.5H8L12 6.5Z"/></svg>""",
    
    'Celestial': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 0L23 12L12 24L1 12L12 0ZM12 6.5C8.9 6.5 6.5 9 6.5 12C6.5 15 8.9 17.5 12 17.5C15.1 17.5 17.5 15 17.5 12C17.5 9 15.1 6.5 12 6.5ZM4.5 12C4.5 10.8 4.8 10 5.5 9C4.2 9.8 3.5 10.8 3.5 12C3.5 13.2 4.2 14.2 5.5 15C4.8 14 4.5 13.2 4.5 12ZM18.5 15C20 14.2 20.5 13.2 20.5 12C20.5 10.8 20 9.8 18.5 9C19.2 10 19.5 10.8 19.5 12C19.5 13.2 19.2 14 18.5 15Z"/></svg>""",
    
    'Stellar': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 1L23 9L17 22H7L1 9L12 1ZM12 16L15.5 18.5L14.5 13.5L18.5 10.5L14 10L12 5.5L10 10L5.5 10.5L9.5 13.5L8.5 18.5L12 16Z"/></svg>""",
    
    'Interstellar': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 0.5L22.5 6.5V17.5L12 23.5L1.5 17.5V6.5L12 0.5ZM12 10.5L8 6.5H16L12 10.5ZM12 13.5L16 17.5H8L12 13.5ZM9 12C9 13.6 10.3 15 12 15C13.7 15 15 13.6 15 12C15 10.4 13.7 9 12 9C10.3 9 9 10.4 9 12Z"/></svg>""",
    
    'Galactic': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 0.5L21.5 5L23 15L17 23.5H7L1 15L2.5 5L12 0.5ZM12 15.5C13.9 15.5 15.5 13.9 15.5 12C15.5 10.1 13.9 8.5 12 8.5C10.1 8.5 8.5 10.1 8.5 12C8.5 13.9 10.1 15.5 12 15.5ZM12 6.5C8.4 6.5 5.5 9.4 5.5 12H7.5C7.5 9.5 9.5 7.5 12 7.5V6.5ZM12 17.5C15.6 17.5 18.5 14.6 18.5 12H16.5C16.5 14.5 14.5 16.5 12 16.5V17.5Z"/></svg>""",
    
    'Intergalactic': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M7.5 0.5H16.5L23.5 7.5V16.5L16.5 23.5H7.5L0.5 16.5V7.5L7.5 0.5ZM12 9C10.3 9 9 10.3 9 12C9 13.7 10.3 15 12 15C13.7 15 15 13.7 15 12C15 10.3 13.7 9 12 9ZM12 5C12.8 5 13.5 5.7 13.5 6.5V8.5C14.5 9 15 9.5 15.5 10.5H17.5C18.3 10.5 19 11.2 19 12C19 12.8 18.3 13.5 17.5 13.5H15.5C15 14.5 14.5 15 13.5 15.5V17.5C13.5 18.3 12.8 19 12 19C11.2 19 10.5 18.3 10.5 17.5V15.5C9.5 15 9 14.5 8.5 13.5H6.5C5.7 13.5 5 12.8 5 12C5 11.2 5.7 10.5 6.5 10.5H8.5C9 9.5 9.5 9 10.5 8.5V6.5C10.5 5.7 11.2 5 12 5Z"/></svg>""",
    
    'Ethereal': """<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 0L19.5 3L23 9.5L21.5 17.5L15.5 23.5H8.5L2.5 17.5L1 9.5L4.5 3L12 0ZM12 6L17 12L12 18L7 12L12 6ZM12 9.5L9 12L12 14.5L15 12L12 9.5Z"/></svg>""",
    
    'Lock': """<svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="11" width="10" height="10" rx="2" /><path d="M12 16v2" stroke="black" stroke-width="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4" fill="none" stroke="currentColor" stroke-width="2"/></svg>"""
}

# ==================================================
#           RANK PROGRESSION LOGIC
# ==================================================

# --- HELPER: ROMAN NUMERALS ---
def to_roman(n):
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ''
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            roman_num += syb[i]
            n -= val[i]
        i += 1
    return roman_num

# --- STATIC RANKS (PHASE 1 - 3) ---
STATIC_RANKS = [
    # --- PHASE 1: THE DEPARTURE (Ice Blue) ---
    {"title": "Observer III", "req": 20, "psyche": "The Telescope", "desc": "Like a lens focusing on the dark, you are learning to view your chaotic thoughts without engaging with them."},
    {"title": "Observer II", "req": 20, "psyche": "The Constellation", "desc": "You no longer see random stars of emotion; you see patterns and shapes in your behavior."},
    {"title": "Observer I", "req": 20, "psyche": "The Overview Effect", "desc": "You have achieved orbit. Looking down at your life from this distance, the storms look peaceful."},
    
    {"title": "Moonwalker III", "req": 50, "psyche": "The Launch", "desc": "You have escaped the gravity of your comfort zone. The silence of this new terrain is heavy, but you are here."},
    {"title": "Moonwalker II", "req": 50, "psyche": "The Dark Side", "desc": "You are walking into the craters of your shadow self, exploring the parts of you that never see the sun."},
    {"title": "Moonwalker I", "req": 50, "psyche": "The Earthrise", "desc": "Standing on your subconscious, you look back at your old identity. It is small, fragile, and beautiful."},

    # --- PHASE 2: THE IGNITION (Solar Gold) ---
    {"title": "Celestial IV", "req": 80, "psyche": "Accretion", "desc": "Like dust forming a world, you are gathering your fragmented memories into a solid, spherical identity."},
    {"title": "Celestial III", "req": 80, "psyche": "Atmosphere", "desc": "You have grown a shield. You burn up the meteors of daily anxiety before they can strike your surface."},
    {"title": "Celestial II", "req": 80, "psyche": "Axial Tilt", "desc": "You accept your internal seasons. You know that your cold winters are just a necessary part of your rotation."},
    {"title": "Celestial I", "req": 80, "psyche": "Gravity", "desc": "You have mass now. You do not chase things; you orbit in your lane and attract what belongs to you."},

    {"title": "Stellar IV", "req": 100, "psyche": "Protostar", "desc": "You realize that the crushing pressure you feel is not destruction; it is the gravity required for ignition."},
    {"title": "Stellar III", "req": 100, "psyche": "Nuclear Fusion", "desc": "Alchemy. You are taking the hydrogen of your pain and fusing it into the helium of wisdom. You generate heat."},
    {"title": "Stellar II", "req": 100, "psyche": "Photosphere", "desc": "You stop reflecting the light of others. You are now the source of light in your own system."},
    {"title": "Stellar I", "req": 100, "psyche": "Main Sequence", "desc": "Stability. You have found the equilibrium between gravity (discipline) and pressure (passion). You burn eternal."},

    {"title": "Interstellar IV", "req": 120, "psyche": "Heliopause", "desc": "You are leaving the magnetic protection of the known. You journal into the deep silence between chapters."},
    {"title": "Interstellar III", "req": 120, "psyche": "The Void", "desc": "There are no stars here to guide you. You must trust your internal navigation systems."},
    {"title": "Interstellar II", "req": 120, "psyche": "Time Dilation", "desc": "In the deep space of healing, time moves differently. A single realization changes years of history."},
    {"title": "Interstellar I", "req": 120, "psyche": "New Horizons", "desc": "You have crossed the great dark. A new system of thought is appearing on your sensors."},

    # --- PHASE 3: THE TRANSCENDENCE (Cosmic Purple) ---
    {"title": "Galactic V", "req": 150, "psyche": "The Spiral Arm", "desc": "You see the structure. Your past trauma and future hope are connected strands in one great design."},
    {"title": "Galactic IV", "req": 150, "psyche": "Rotation Curve", "desc": "You stop fighting the spin. You move with the flow of the universe, trusting the velocity of your life."},
    {"title": "Galactic III", "req": 150, "psyche": "Dark Matter", "desc": "You acknowledge the invisible forces—your subconscious drives—that hold your visible life together."},
    {"title": "Galactic II", "req": 150, "psyche": "Supermassive Core", "desc": "You face the hole at your center. You realize it is not emptiness, but infinite density and potential."},
    {"title": "Galactic I", "req": 150, "psyche": "The Ecosystem", "desc": "You are not a solitary star. You contain billions of moments, a complex galaxy of self."},

    {"title": "Intergalactic V", "req": 180, "psyche": "The Filament", "desc": "You sense the web. Through writing, you connect your story to the universal human experience."},
    {"title": "Intergalactic IV", "req": 180, "psyche": "The Great Void", "desc": "There is no up or down in space. You release the rigid definitions of success or failure."},
    {"title": "Intergalactic III", "req": 180, "psyche": "Redshift", "desc": "You are expanding. You are moving away from your origin point so fast that the light of the past changes color."},
    {"title": "Intergalactic II", "req": 180, "psyche": "The Great Attractor", "desc": "You are being pulled toward a destiny you cannot see but can feel. You trust the pull."},
    {"title": "Intergalactic I", "req": 180, "psyche": "Cosmic Scale", "desc": "Ego death. Your daily anxieties are merely dust against the background radiation of your spirit."},
]

# --- DYNAMIC RANKS (PHASE 4: ETHEREAL ASCENSION) ---
ETHEREAL_RANKS = []
base_req = 200  # Starting cost for Ethereal I

ethereal_states = [
    {"name": "The Nebula", "desc": "Form becomes fluid. You realize you can reshape your narrative at will. You are the cloud before the star."},
    {"name": "Quantum Superposition", "desc": "You accept contradiction. You can be both sad and grateful, lost and found, simultaneously."},
    {"name": "Entanglement", "desc": "You understand that nothing is separate. Your past self and future self are communicating across time."},
    {"name": "Relativity", "desc": "Your perspective defines your reality. By changing how you view the past, you physically change its weight."},
    {"name": "The Singularity", "desc": "Focus becomes infinite. The barrier between the writer and the written word dissolves."},
    {"name": "The Big Bang", "desc": "Creation. You speak, and a new universe is born. You are the author of your reality."},
    {"name": "Dark Energy", "desc": "Expansion. You are growing faster than the universe can contain you. You push boundaries effortlessly."},
    {"name": "Cosmic Background", "desc": "Memory. You carry the heat of your creation, but it no longer burns; it just sustains you."},
    {"name": "The Multiverse", "desc": "Possibility. You see every choice you didn't make not as a loss, but as a life lived elsewhere."},
    {"name": "The Source", "desc": "You return to the beginning, but with full knowledge. You are the Universe experiencing itself."}
]

# Generate Ethereal I to Ethereal X (10 levels)
for i in range(1, 11):
    roman = to_roman(i)
    cost = base_req + ((i - 1) * 100) # 200, 300, 400...
    state = ethereal_states[i-1]
    
    ETHEREAL_RANKS.append({
        "title": f"Ethereal {roman}",
        "req": cost,
        "psyche": state["name"],
        "desc": state["desc"]
    })

RANK_SYSTEM = STATIC_RANKS + ETHEREAL_RANKS

# ==================================================
#           DAILY REWARD & STREAK LOGIC
# ==================================================

def check_entry_quality(msg):
    """
    Quality control: Entry must be > 30 chars to earn Stardust.
    """
    if len(msg.strip()) < 30:
        return False
    return True

def process_daily_rewards(users_col, user_id, msg):
    """
    Calculates Daily Rewards, Streaks, and Constellation Bonuses.
    Returns: { 'awarded': bool, 'total_gain': int, 'message': str, 'event': str }
    """
    if users_col is None: return {'awarded': False}

    # 1. QUALITY CHECK
    if not check_entry_quality(msg):
        return {'awarded': False, 'message': "Entry too short for Stardust."}

    user = users_col.find_one({"user_id": user_id})
    if not user: return {'awarded': False}

    today_str = datetime.now().strftime("%Y-%m-%d")
    last_reward = user.get("last_reward_date") 
    current_streak = user.get("current_streak", 0)
    current_dust = user.get("stardust", 0)
    stars_count = user.get("star_count", 0) 

    # 2. CHECK IF ALREADY REWARDED TODAY
    if last_reward == today_str:
        return {'awarded': False, 'message': "Daily reward already claimed."}

    # 3. CALCULATE STREAK
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if last_reward == yesterday_str:
        current_streak += 1
    else:
        current_streak = 1 # Reset streak if missed a day

    # 4. CALCULATE REWARDS
    base_sd = 5
    streak_sd = base_sd * current_streak
    
    # 5. CONSTELLATION BONUS (Every 7th Star/Entry)
    stars_count += 1
    constellation_bonus = 0
    is_constellation_complete = (stars_count % 7 == 0)
    
    if is_constellation_complete:
        constellation_bonus = 10
    
    total_gain = streak_sd + constellation_bonus
    new_dust = current_dust + total_gain
    
    # 6. UPDATE DB
    users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "stardust": new_dust,
                "current_streak": current_streak,
                "last_reward_date": today_str,
                "star_count": stars_count
            }
        }
    )

    # 7. FORMAT FEEDBACK MESSAGE
    event_type = "daily_reward"
    msg_text = f"+{streak_sd} SD (Streak x{current_streak})"
    
    if constellation_bonus: 
        msg_text += f"\n+10 SD (Constellation Completed!)"
        event_type = "constellation_complete"

    return {
        'awarded': True, 
        'total_gain': total_gain, 
        'message': msg_text,
        'event': event_type
    }

def update_rank_check(users_col, user_id):
    """
    Checks if current stardust is enough to Level Up.
    Does NOT award XP, just processes Rank Changes.
    """
    if users_col is None: return None
    
    user = users_col.find_one({"user_id": user_id})
    current_idx = user.get("rank_index", 0)
    current_dust = user.get("stardust", 0)
    
    rank_data = RANK_SYSTEM[current_idx] if current_idx < len(RANK_SYSTEM) else RANK_SYSTEM[-1]
    req = rank_data['req']
    
    if current_dust >= req and current_idx < len(RANK_SYSTEM) - 1:
        new_dust = current_dust - req # Carry over overflow
        current_idx += 1
        new_rank = RANK_SYSTEM[current_idx]['title']
        
        users_col.update_one({"user_id": user_id}, {
            "$set": {"rank_index": current_idx, "rank": new_rank, "stardust": new_dust}
        })
        return "level_up"
    return None

def get_rank_meta(idx):
    """Returns the metadata (req, psyche, desc, svg, color) for a given rank index."""
    if idx < 0: idx = 0
    if idx >= len(RANK_SYSTEM): idx = len(RANK_SYSTEM) - 1
    
    data = RANK_SYSTEM[idx].copy()
    
    # Inject Assets based on Rank Title Prefix
    base_name = data['title'].split(' ')[0]
    data['svg'] = RANK_ICONS.get(base_name, RANK_ICONS.get('Observer'))
    data['color'] = PHASE_COLORS.get(base_name, "#00f2fe")
    
    return data

def get_all_ranks_data():
    """Returns full rank list with Assets for the Modal."""
    enriched_list = []
    for rank in RANK_SYSTEM:
        r = rank.copy()
        base_name = r['title'].split(' ')[0]
        r['svg'] = RANK_ICONS.get(base_name, RANK_ICONS.get('Observer'))
        r['color'] = PHASE_COLORS.get(base_name, "#00f2fe")
        enriched_list.append(r)
    
    return {
        "ranks": enriched_list,
        "lock_icon": RANK_ICONS['Lock']
    }
