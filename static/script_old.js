const SQ_MAP = { "mother_maiden": "What is your mother's maiden name?", "first_pet": "What was the name of your first pet?", "birth_city": "In what city were you born?", "favorite_book": "What is your favorite book?", "first_school": "What was the name of your first school?" };
let isProcessing = false; let currentCalendarDate = new Date(); let fullChatHistory = {}; let userHistoryDates = []; let currentMode = 'journal'; let activeMediaFile = null; let activeAudioFile = null; let globalRankTree = null; let currentLockIcon = '';
const STAR_SVG = `<svg class="star-point" viewBox="0 0 24 24"><path d="M12 2l2.4 7.2h7.6l-6 4.8 2.4 7.2-6-4.8-6 4.8 2.4-7.2-6-4.8h7.6z"/></svg>`;

// --- ICONS ---
const ICON_SUCCESS = `<svg class="w-10 h-10 text-green-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
const ICON_ERROR = `<svg class="w-10 h-10 text-red-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
const ICON_SPEAK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
const ICON_CHEVRON = `<svg class="group-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>`;

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

// --- GALAXY ENGINE ---
const canvas = document.getElementById('starfield'); const ctx = canvas.getContext('2d'); 
let animationFrameId; let isGalaxyActive = false; 
let galaxyData = []; let ambientStars = []; 

function resizeStars() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; } window.addEventListener('resize', resizeStars); resizeStars();

function initAmbientStars() {
    ambientStars = [];
    for(let i=0; i<200; i++) {
        ambientStars.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            r: Math.random() * 1.2,
            opacity: Math.random() * 0.4 + 0.1,
            speed: Math.random() * 0.05 + 0.02
        });
    }
}

canvas.addEventListener('click', (e) => { if(!isGalaxyActive) return; const rect = canvas.getBoundingClientRect(); const x = e.clientX - rect.left; const y = e.clientY - rect.top; galaxyData.forEach(star => { if(Math.hypot(x-star.x, y-star.y) < 20) openArchive(star.id); }); });

async function toggleGalaxy() { 
    const btn = document.getElementById('galaxy-btn'); 
    isGalaxyActive = !isGalaxyActive; 
    if (isGalaxyActive) { 
        btn.classList.add('galaxy-open'); btn.innerHTML = '✕'; 
        document.body.classList.add('galaxy-mode'); SonicAtmosphere.playMode('galaxy'); 
        initAmbientStars();
        const res = await fetch('/api/galaxy_map'); const data = await res.json(); 
        galaxyData = data.map(d => ({ 
            ...d, x: Math.random() * (canvas.width - 40) + 20, y: Math.random() * (canvas.height - 40) + 20, 
            r: d.type === 'void' ? 3 : 5, color: d.type === 'void' ? '#ef4444' : '#ffffff', 
            vx: (Math.random() - 0.5) * 0.2, vy: (Math.random() - 0.5) * 0.2 
        })); 
        animateStars(); 
    } else { 
        btn.classList.remove('galaxy-open'); 
        btn.innerHTML = `<svg id="galaxy-icon-svg" viewBox="0 0 24 24"><g fill="currentColor" stroke="currentColor" stroke-width="0.8"><circle cx="12" cy="12" r="2.5" fill="black" stroke="none" /><path d="M12 12 C14.5 12 16 10 16 8 C16 6 14 5 12 5" fill="none" stroke-linecap="round" stroke-dasharray="1 1" /><path d="M12 12 C12 14.5 14 16 16 16 C18 16 19 14 19 12" fill="none" stroke-linecap="round" stroke-dasharray="1 1" /><path d="M12 12 C9.5 12 8 14 8 16 C8 18 10 19 12 19" fill="none" stroke-linecap="round" stroke-dasharray="1 1" /><path d="M12 12 C12 9.5 10 8 8 8 C6 8 5 10 5 12" fill="none" stroke-linecap="round" stroke-dasharray="1 1" /><circle cx="8" cy="8" r="0.5" fill="black" stroke="none" /><circle cx="16" cy="16" r="0.5" fill="black" stroke="none" /><circle cx="16" cy="8" r="0.5" fill="black" stroke="none" /><circle cx="8" cy="16" r="0.5" fill="black" stroke="none" /></g></svg>`; 
        document.body.classList.remove('galaxy-mode'); SonicAtmosphere.playMode('journal'); 
        cancelAnimationFrame(animationFrameId); ctx.clearRect(0,0,canvas.width,canvas.height); 
    } 
}

function animateStars() { 
    if(!isGalaxyActive) return; ctx.clearRect(0,0,canvas.width,canvas.height); 
    ctx.fillStyle = "rgba(255, 255, 255, 0.3)"; ctx.shadowBlur = 0; 
    ambientStars.forEach(star => { star.y -= star.speed; if(star.y < 0) star.y = canvas.height; ctx.beginPath(); ctx.arc(star.x, star.y, star.r, 0, Math.PI*2); ctx.fill(); });
    galaxyData.forEach(star => { star.x += star.vx; star.y += star.vy; if(star.x < 0 || star.x > canvas.width) star.vx *= -1; if(star.y < 0 || star.y > canvas.height) star.vy *= -1; if (star.type === 'void') { galaxyData.forEach(other => { if (other !== star && Math.hypot(star.x - other.x, star.y - other.y) < 150) { other.vx += (star.x - other.x) * 0.0001; other.vy += (star.y - other.y) * 0.0001; } }); } }); 
    ctx.lineWidth = 0.5; ctx.strokeStyle = "rgba(255,255,255,0.15)"; 
    galaxyData.forEach((star, i) => { 
        if (star.x < -10 || star.x > canvas.width + 10 || star.y < -10 || star.y > canvas.height + 10) return; 
        if (galaxyData[i+1] && galaxyData[i+1].group === star.group) { ctx.beginPath(); ctx.moveTo(star.x, star.y); ctx.lineTo(galaxyData[i+1].x, galaxyData[i+1].y); ctx.stroke(); } 
        ctx.beginPath(); ctx.arc(star.x, star.y, star.r, 0, Math.PI*2); ctx.fillStyle = star.color; ctx.shadowBlur = 15; ctx.shadowColor = star.color; ctx.fill(); 
        if (star.constellation_name) { ctx.font = "10px monospace"; ctx.fillStyle = "rgba(255,255,255,0.8)"; ctx.fillText(star.constellation_name, star.x + 10, star.y); } 
    }); 
    animationFrameId = requestAnimationFrame(animateStars); 
}

async function loadData() { 
    try { 
        const res = await fetch('/api/data'); if(!res.ok) return; 
        const data = await res.json(); 
        if(data.status === 'guest') { window.location.href='/login'; return; } 
        
        globalRankTree = data.progression_tree; currentLockIcon = data.progression_tree.lock_icon; 
        const hour = new Date().getHours(); let timeGreet = hour >= 18 ? "Good Evening" : (hour >= 12 ? "Good Afternoon" : "Good Morning");
        document.getElementById('greeting-text').innerText = `${timeGreet}, ${data.first_name}!`; 
        document.getElementById('rank-display').innerText = data.rank; 
        document.getElementById('rank-psyche').innerText = data.rank_psyche; 
        document.getElementById('rank-progress-bar').style.width = `${data.rank_progress}%`; 
        document.getElementById('stardust-cnt').innerText = `${data.stardust_current}/${data.stardust_max} Stardust`; 
        
        document.getElementById('pfp-img').src = data.profile_pic || ''; 
        document.documentElement.style.setProperty('--mood', data.current_color); 
        document.getElementById('main-rank-icon').innerHTML = data.current_svg; 
        document.getElementById('profile-pfp-large').src = data.profile_pic || ''; 
        document.getElementById('profile-fullname').innerText = `${data.first_name} ${data.last_name}`; 
        document.getElementById('profile-id').innerText = data.username; 
        document.getElementById('profile-color-text').innerText = data.aura_color; 
        
        const dot = document.getElementById('profile-color-dot'); dot.style.backgroundColor = data.aura_color;
        if (!data.aura_color || dot.style.backgroundColor === '') dot.style.backgroundColor = data.current_color;

        document.getElementById('profile-secret-q').innerText = SQ_MAP[data.secret_question] || data.secret_question;
        document.getElementById('edit-fname').value = data.first_name; 
        document.getElementById('edit-lname').value = data.last_name; 
        document.getElementById('edit-color').value = data.aura_color; 
        document.getElementById('edit-uid-display').innerText = data.username;
        document.getElementById('theme-btn').innerText = document.documentElement.getAttribute('data-theme') === 'light' ? 'Light' : 'Dark';
        
        if(data.history) fullChatHistory = data.history; 
        userHistoryDates = Object.values(data.history).map(e=>e.date); 
        renderCalendar(); 
    } catch(e) { console.error(e); } 
}

async function handlePfpUpload() { const input = document.getElementById('pfp-upload-input'); if(input.files && input.files[0]) { const formData = new FormData(); formData.append('pfp', input.files[0]); const res = await fetch('/api/update_pfp', { method: 'POST', body: formData }); const data = await res.json(); if(data.status === 'success') { document.getElementById('pfp-img').src = data.url; document.getElementById('profile-pfp-large').src = data.url; } } }
function showStatus(success, msg) { document.getElementById('status-icon').innerHTML = success ? ICON_SUCCESS : ICON_ERROR; document.getElementById('status-title').innerText = success ? "Success" : "Error"; document.getElementById('status-msg').innerText = msg; openModal('status-modal'); }
function askUpdateInfo() { openModal('info-confirm-modal'); }
async function confirmUpdateInfo() { const btn = document.getElementById('btn-confirm-info'); const originalText = "Confirm"; btn.innerHTML = '<span class="spinner"></span>'; btn.disabled = true; const body = { first_name: document.getElementById('edit-fname').value, last_name: document.getElementById('edit-lname').value, aura_color: document.getElementById('edit-color').value }; try { const res = await fetch('/api/update_profile', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }); const data = await res.json(); if(data.status === 'success') { closeModal('info-confirm-modal'); closeModal('edit-info-modal'); showStatus(true, "Profile Updated"); loadData(); } else { showStatus(false, data.message); } } catch(e) { showStatus(false, "Connection Failed"); } btn.innerHTML = originalText; btn.disabled = false; }
async function updateSecurity(type) { let body = {}; const btn = type === 'pass' ? document.getElementById('btn-update-pass') : document.getElementById('btn-update-secret'); const originalText = "Update"; btn.innerHTML = '<span class="spinner"></span> Loading...'; btn.disabled = true; if(type === 'pass') { const p1 = document.getElementById('new-pass-input').value; const p2 = document.getElementById('confirm-pass-input').value; if(p1 !== p2) { document.getElementById('new-pass-input').classList.add('input-error'); document.getElementById('confirm-pass-input').classList.add('input-error'); setTimeout(()=>{ document.getElementById('new-pass-input').classList.remove('input-error'); document.getElementById('confirm-pass-input').classList.remove('input-error'); }, 500); btn.innerHTML=originalText; btn.disabled=false; return; } body = { new_password: p1 }; } else { const q = document.getElementById('new-secret-q').value; if(!q) { showStatus(false, "Select a Question"); btn.innerHTML=originalText; btn.disabled=false; return; } body = { new_secret_q: q, new_secret_a: document.getElementById('new-secret-a').value }; } try { const res = await fetch('/api/update_security', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }); const data = await res.json(); if(data.status === 'success') { closeModal('change-pass-modal'); closeModal('change-secret-modal'); showStatus(true, "Security details updated."); loadData(); } else { showStatus(false, data.message); } } catch(e) { showStatus(false, "Connection Failed"); } btn.innerHTML = originalText; btn.disabled = false; }
async function performWipe() { const btn = document.querySelector('#delete-confirm-modal button.bg-red-500'); const originalText = btn.innerText; btn.innerText = "Deleting..."; btn.disabled = true; try { const res = await fetch('/api/clear_history', { method: 'POST' }); const data = await res.json(); if (data.status === 'success') { window.location.href = '/login'; } else { alert("Error: " + data.message); btn.innerText = originalText; btn.disabled = false; } } catch (e) { alert("Connection failed."); btn.innerText = originalText; btn.disabled = false; } }

// --- RANK MODAL LOGIC (V10.0: Icon Inject + Height Fix) ---
function openRanksModal() { 
    if (!globalRankTree) return; 
    
    const container = document.getElementById('ranks-list-container'); 
    container.innerHTML = ''; 
    container.className = 'tree-container'; 
    
    const modal = document.getElementById('ranks-modal'); 
    modal.style.display = 'flex'; 
    setTimeout(() => modal.classList.add('active'), 10); 
    
    document.getElementById('modal-rank-icon').innerHTML = document.getElementById('main-rank-icon').innerHTML; 
    document.getElementById('modal-rank-name').innerText = document.getElementById('rank-display').innerText; 
    document.getElementById('modal-psyche-display').innerText = document.getElementById('rank-psyche').innerText;
    document.getElementById('modal-progress-bar').style.width = document.getElementById('rank-progress-bar').style.width; 
    document.getElementById('modal-sd-text').innerText = document.getElementById('stardust-cnt').innerText; 
    
    const normalize = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
    const currentTitleRaw = document.getElementById('rank-display').innerText;
    const currentTitleNorm = normalize(currentTitleRaw);
    const flatList = globalRankTree.ranks;
    const currentFlatIndex = flatList.findIndex(r => normalize(r.title) === currentTitleNorm);

    if(currentFlatIndex !== -1) {
        document.getElementById('modal-synth-text').innerText = flatList[currentFlatIndex].desc;
    } else {
        document.getElementById('modal-synth-text').innerText = flatList[0].desc;
    }

    const groupedRanks = {};
    flatList.forEach((rank, index) => {
        const mainName = rank.title.split(' ')[0]; 
        if (!groupedRanks[mainName]) {
            // V10.0: Capture the FIRST icon of the group
            groupedRanks[mainName] = { 
                name: mainName, 
                subRanks: [], 
                isActiveGroup: false,
                icon: rank.svg // Auto-captures the SVG of the first item (e.g. Observer I)
            };
        }
        
        const isCurrentNode = (index === currentFlatIndex);
        if (isCurrentNode) groupedRanks[mainName].isActiveGroup = true;

        groupedRanks[mainName].subRanks.push({
            ...rank,
            globalIndex: index,
            isCurrent: isCurrentNode,
            isUnlocked: index <= currentFlatIndex
        });
    });

    Object.values(groupedRanks).forEach(group => {
        const groupEl = document.createElement('div');
        groupEl.className = `rank-group ${group.isActiveGroup ? 'open active' : ''}`;
        
        // V10.0: Determine Lock State for Group Header
        // If the first rank is unlocked, group is unlocked.
        const isGroupUnlocked = group.subRanks[0].isUnlocked;
        const lockClass = isGroupUnlocked ? '' : 'locked';

        const header = document.createElement('div');
        header.className = `group-header ${lockClass}`;
        
        // V10.0: Inject Icon on Left
        header.innerHTML = `
            <div class="group-label">
                <div class="group-left-icon">${group.icon}</div>
                <span class="group-title">${group.name}</span>
            </div>
            <div class="group-icon">${ICON_CHEVRON}</div>
        `;
        
        header.onclick = () => {
            document.querySelectorAll('.rank-group').forEach(el => { if (el !== groupEl) el.classList.remove('open'); });
            groupEl.classList.toggle('open');
            setTimeout(() => groupEl.scrollIntoView({behavior: 'smooth', block: 'center'}), 300);
        };
        groupEl.appendChild(header);

        const subList = document.createElement('div');
        subList.className = 'rank-sublist';

        group.subRanks.forEach(sub => {
            const node = document.createElement('div');
            node.className = `sub-node ${sub.isUnlocked ? 'unlocked' : ''} ${sub.isCurrent ? 'current' : ''}`;
            
            let status = sub.desc;
            if (sub.isCurrent) status = "Current Status";
            else if (!sub.isUnlocked) status = "Locked";

            node.innerHTML = `
                <div class="flex-1">
                    <div class="sub-title">${sub.title}</div>
                    <div class="sub-desc">${status}</div>
                </div>
                ${sub.isUnlocked ? '<div class="text-[var(--mood)]">✔</div>' : '<div class="opacity-30">🔒</div>'}
            `;
            subList.appendChild(node);
        });

        groupEl.appendChild(subList);
        container.appendChild(groupEl);
    });
    
    setTimeout(() => { 
        const active = container.querySelector('.rank-group.active'); 
        if(active) active.scrollIntoView({behavior: 'smooth', block: 'center'}); 
    }, 200); 
}

function getStarsHTML(rankTitle) { let count = 0; if (rankTitle.includes("VI")) count = 6; else if (rankTitle.includes("IV")) count = 4; else if (rankTitle.includes("V")) count = 5; else if (rankTitle.includes("III")) count = 3; else if (rankTitle.includes("II")) count = 2; else if (rankTitle.includes("I")) count = 1; if(rankTitle.includes("Ethereal") && count > 5) count = 5; return Array(count).fill(STAR_SVG).join(''); }
function handleFileSelect() { const input = document.getElementById('img-upload'); if(input.files && input.files[0]) { activeMediaFile = input.files[0]; document.getElementById('chat-input').placeholder = "Image attached. Add context..."; } }
function handleAudioSelect() { const input = document.getElementById('audio-upload'); if(input.files && input.files[0]) { activeAudioFile = input.files[0]; document.getElementById('chat-input').placeholder = "Audio attached. Transmitting..."; sendMessage(); } }
function toggleMic() { document.getElementById('audio-upload').click(); }

function parseMarkdown(text) {
    if (!text) return "";
    let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>').replace(/\n/g, '<br>');
    return html;
}

function showTyping() { document.getElementById('typing-indicator').classList.remove('hidden'); document.getElementById('chat-history').scrollTop = 9999; }
function hideTyping() { document.getElementById('typing-indicator').classList.add('hidden'); }

function speakText(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1; utterance.pitch = 1;
        window.speechSynthesis.speak(utterance);
    } else { alert("Voice synthesis not supported."); }
}

async function sendMessage() { 
    if(isProcessing) return; 
    const input = document.getElementById('chat-input'); 
    const msg = input.value.trim(); 
    if(!msg && !activeMediaFile && !activeAudioFile) return; 
    
    appendMsg(msg || "[Media Transmitting...]", 'user'); 
    input.value=''; isProcessing=true; showTyping();

    const formData = new FormData(); 
    formData.append('message', msg); formData.append('mode', currentMode); 
    if(activeMediaFile) formData.append('media', activeMediaFile); 
    if(activeAudioFile) formData.append('audio', activeAudioFile); 
    
    try { 
        const res = await fetch('/api/process', { method:'POST', body: formData }); 
        const data = await res.json(); 
        hideTyping(); appendMsg(data.reply, 'ai'); 
        if(data.command === 'daily_reward' || data.command === 'level_up') spawnStardust(); 
        if(data.command === 'switch_to_void') setTimeout(()=>openChat('rant'), 1000); 
        activeMediaFile = null; activeAudioFile = null; 
        document.getElementById('chat-input').placeholder = "Signal..."; 
        await loadData(); 
    } catch(e) { hideTyping(); appendMsg("Transmission failed.", 'ai'); } 
    isProcessing=false; 
}

function appendMsg(txt, sender) { 
    const div = document.createElement('div'); div.className = `msg msg-${sender}`; div.innerHTML = parseMarkdown(txt); 
    if (sender === 'ai') {
        const btn = document.createElement('span'); btn.className = 'voice-play-btn'; btn.innerHTML = ICON_SPEAK;
        const cleanText = txt.replace(/\*\*/g, '').replace(/\*/g, '');
        btn.onclick = () => speakText(cleanText); div.appendChild(btn);
    }
    const history = document.getElementById('chat-history'); const indicator = document.getElementById('typing-indicator');
    history.insertBefore(div, indicator); history.scrollTop = 9999; 
}

function openArchive(id) { const modal = document.getElementById('archive-modal'); modal.classList.add('active'); fetch('/api/star_detail', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})}).then(r=>r.json()).then(d=>{ document.getElementById('archive-date').innerText = d.date; document.getElementById('archive-analysis').innerText = d.analysis || "Analysis corrupted."; const imgContainer = document.getElementById('archive-image-container'); if(d.image_url) { imgContainer.classList.remove('hidden'); document.getElementById('archive-image').src = d.image_url; } else { imgContainer.classList.add('hidden'); } const audioContainer = document.getElementById('archive-audio-container'); const audioEl = document.getElementById('archive-audio'); if(d.audio_url) { audioContainer.classList.remove('hidden'); audioEl.src = d.audio_url; } else { audioContainer.classList.add('hidden'); } }); }
function openChat(mode) { currentMode = mode; SonicAtmosphere.playMode(mode); document.getElementById('chat-overlay').classList.add('active'); const w = document.getElementById('chat-modal-window'); w.className = `chat-window origin-${mode === 'rant' ? 'void' : 'ai'}`; document.getElementById('chat-header-title').innerText = mode === 'rant' ? "THE VOID" : "CELI AI"; renderChatHistory(fullChatHistory); }
function closeChat() { document.getElementById('chat-overlay').classList.remove('active'); SonicAtmosphere.playMode('journal'); }
function openModal(id) { document.getElementById(id).style.display='flex'; }
function closeModal(id) { document.getElementById(id).classList.remove('active'); document.getElementById(id).style.display='none'; }
function closeArchive() { document.getElementById('archive-modal').classList.remove('active'); document.getElementById('archive-audio').pause(); }
function spawnStardust() { const s=document.getElementById('nav-pfp').getBoundingClientRect(); const t=document.getElementById('rank-progress-bar').getBoundingClientRect(); const pfp=document.getElementById('nav-pfp'); pfp.classList.remove('pulse-anim'); void pfp.offsetWidth; pfp.classList.add('pulse-anim'); for(let i=0;i<8;i++){ setTimeout(()=>{ const p=document.createElement('div'); p.className='stardust-particle'; p.style.left=(s.left+s.width/2)+'px'; p.style.top=(s.top+s.height/2)+'px'; document.body.appendChild(p); const tx=t.left+Math.random()*t.width; const ty=t.top+t.height/2; p.animate([{transform:'translate(0,0) scale(1)',opacity:1},{transform:`translate(${tx-parseFloat(p.style.left)}px, ${ty-parseFloat(p.style.top)}px) scale(0.5)`,opacity:0}],{duration:800+Math.random()*400,easing:'cubic-bezier(0.25,1,0.5,1)'}).onfinish=()=>p.remove(); },i*100); } }
function renderCalendar() { const g=document.getElementById('cal-grid'); g.innerHTML=''; const m=currentCalendarDate.getMonth(); const y=currentCalendarDate.getFullYear(); document.getElementById('cal-month-year').innerText=new Date(y,m).toLocaleString('default',{month:'long',year:'numeric'}); ["S","M","T","W","T","F","S"].forEach(d=>g.innerHTML+=`<div>${d}</div>`); const days=new Date(y,m+1,0).getDate(); const f=new Date(y,m,1).getDay(); for(let i=0;i<f;i++)g.innerHTML+=`<div></div>`; for(let i=1;i<=days;i++){ const d=document.createElement('div'); d.className='cal-day'; d.innerText=i; if(userHistoryDates.includes(`${y}-${String(m+1).padStart(2,'0')}-${String(i).padStart(2,'0')}`)) d.classList.add('has-entry'); g.appendChild(d); } }
function changeMonth(d) { currentCalendarDate.setMonth(currentCalendarDate.getMonth()+d); renderCalendar(); }
function renderChatHistory(h) { 
    const c = document.getElementById('chat-history'); 
    Array.from(c.children).forEach(child => { if(child.id !== 'typing-indicator') c.removeChild(child); });
    Object.keys(h).sort().slice(-50).forEach(k => { appendMsg(h[k].summary||"Entry", 'user'); appendMsg(h[k].reply, 'ai'); }); 
}
async function clearMemory() { openModal('delete-confirm-modal'); }
window.onload = loadData;
