// --- GLOBAL STATE ---
const SQ_MAP = { "mother_maiden": "What is your mother's maiden name?", "first_pet": "What was the name of your first pet?", "birth_city": "In what city were you born?", "favorite_book": "What is your favorite book?", "first_school": "What was the name of your first school?" };
let isProcessing = false; 
let currentCalendarDate = new Date(); 
let fullChatHistory = {}; 
let userHistoryDates = []; 
let currentMode = 'journal'; 
let activeMediaFile = null; 
let activeAudioFile = null; 
let globalRankTree = null; 
let currentLockIcon = '';

// --- CONSTANTS ---
const STAR_SVG = `<svg class="star-point" viewBox="0 0 24 24"><path d="M12 2l2.4 7.2h7.6l-6 4.8 2.4 7.2-6-4.8-6 4.8 2.4-7.2-6-4.8h7.6z"/></svg>`;
const ICON_SUCCESS = `<svg class="w-10 h-10 text-green-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
const ICON_ERROR = `<svg class="w-10 h-10 text-red-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
const ICON_SPEAK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
const ICON_CHEVRON = `<svg class="group-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>`;

// --- AI SIGNAL SYSTEM (HUMANIZED) ---
const AI_PROMPTS = [
    "How are you feeling right now?",
    "Tell me about your day.",
    "I'm here if you need to vent.",
    "Did you get that thing done?",
    "What's on your mind?",
    "Want to talk about it?",
    "I'm listening."
];

function triggerAiSignal() {
    const bubble = document.getElementById('ai-signal-bubble');
    const text = document.getElementById('ai-signal-text');
    
    // Pick random prompt
    const prompt = AI_PROMPTS[Math.floor(Math.random() * AI_PROMPTS.length)];
    text.innerText = prompt;
    
    // Show Bubble (2s delay)
    setTimeout(() => {
        bubble.classList.add('visible');
    }, 2000); 

    // Auto-hide (10s delay)
    setTimeout(() => {
        bubble.classList.remove('visible');
    }, 10000);
}

// --- UTILS ---
function openModal(id) { document.getElementById(id).style.display='flex'; }
function closeModal(id) { document.getElementById(id).classList.remove('active'); document.getElementById(id).style.display='none'; }
function showStatus(success, msg) { document.getElementById('status-icon').innerHTML = success ? ICON_SUCCESS : ICON_ERROR; document.getElementById('status-title').innerText = success ? "Success" : "Error"; document.getElementById('status-msg').innerText = msg; openModal('status-modal'); }

function toggleTheme() {
    const html = document.documentElement;
    const btn = document.getElementById('theme-btn');
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        btn.innerText = "Dark";
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        btn.innerText = "Light";
        localStorage.setItem('theme', 'light');
    }
    if(typeof galaxyData !== 'undefined' && isGalaxyActive) {
        galaxyData.forEach(d => { if(d.color !== '#ef4444') d.color = (html.getAttribute('data-theme') === 'light' ? '#000' : '#fff'); });
    }
}
const savedTheme = localStorage.getItem('theme');
if(savedTheme === 'light') { document.documentElement.setAttribute('data-theme', 'light'); }

const SonicAtmosphere = { 
    ctx: null, nodes: [], active: false, 
    init: function() { if(this.ctx) return; const AudioContext = window.AudioContext || window.webkitAudioContext; this.ctx = new AudioContext(); }, 
    toggle: function() { this.init(); if(this.ctx.state === 'suspended') this.ctx.resume(); this.active = !this.active; if(this.active) this.playMode(currentMode); else this.stop(); }, 
    playMode: function(mode) { if(!this.active) return; this.stop(); const t = this.ctx.currentTime; const osc = this.ctx.createOscillator(); const gain = this.ctx.createGain(); osc.type = mode === 'journal' ? 'sine' : 'triangle'; osc.frequency.setValueAtTime(mode === 'journal' ? 220 : 55, t); gain.gain.setValueAtTime(0, t); gain.gain.linearRampToValueAtTime(mode === 'journal' ? 0.05 : 0.1, t+2); osc.connect(gain); gain.connect(this.ctx.destination); osc.start(); this.nodes.push({stop: ()=> { gain.gain.linearRampToValueAtTime(0, this.ctx.currentTime+1); setTimeout(()=>osc.stop(), 1000); }}); }, 
    stop: function() { this.nodes.forEach(n => n.stop()); this.nodes = []; } 
};
