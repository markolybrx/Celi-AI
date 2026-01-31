// --- DATA & CALENDAR LOGIC (RESTORED) ---

let pickerDate = new Date();
let selectedMonthIdx = 0;

async function loadData() { 
    try { 
        // 1. Standard Fetch
        const res = await fetch('/api/data'); 
        if(!res.ok) return; 
        
        const data = await res.json(); 
        if(data.status === 'guest') { window.location.href='/login'; return; } 

        renderData(data);
    } catch(e) { 
        console.error("CRITICAL DATA ERROR:", e); 
    } 
}

function renderData(data) {
    // DASHBOARD
    if (data.progression_tree) globalRankTree = data.progression_tree;
    
    const safeSet = (id, val) => { const el = document.getElementById(id); if(el) el.innerText = val; };
    const safeSrc = (id, val) => { const el = document.getElementById(id); if(el) el.src = val || ''; };

    safeSet('greeting-text', `Welcome back, ${data.first_name || 'Traveler'}!`); 
    safeSet('rank-display', data.rank || 'Observer III'); 
    safeSet('stardust-cnt', `${data.stardust_current || 0}/${data.stardust_max || 100} Stardust`); 
    
    const progressBar = document.getElementById('rank-progress-bar');
    if(progressBar) progressBar.style.width = `${data.rank_progress || 0}%`; 

    // PROFILE
    safeSrc('pfp-img', data.profile_pic); 
    safeSrc('profile-pfp-large', data.profile_pic); 
    safeSet('profile-fullname', `${data.first_name} ${data.last_name || ''}`); 
    safeSet('profile-id', data.username); 

    const editFname = document.getElementById('edit-fname'); if(editFname) editFname.value = data.first_name || '';
    const editLname = document.getElementById('edit-lname'); if(editLname) editLname.value = data.last_name || '';

    // HISTORY
    if(data.history) fullChatHistory = data.history; 
    else fullChatHistory = {};
    
    // TRIVIA
    const triviaText = document.getElementById('daily-trivia-text');
    if (triviaText && data.daily_trivia) triviaText.innerText = `"${data.daily_trivia.fact}"`;

    renderCalendar(); 
}

// --- UTILITY FUNCTIONS ---
async function handlePfpUpload() { const input = document.getElementById('pfp-upload-input'); if(input.files && input.files[0]) { const formData = new FormData(); formData.append('pfp', input.files[0]); const res = await fetch('/api/update_pfp', { method: 'POST', body: formData }); const data = await res.json(); if(data.status === 'success') { document.getElementById('pfp-img').src = data.url; document.getElementById('profile-pfp-large').src = data.url; } } }
function askUpdateInfo() { openModal('info-confirm-modal'); }
async function confirmUpdateInfo() { const btn = document.getElementById('btn-confirm-info'); const originalText = "Confirm"; btn.innerHTML = '...'; btn.disabled = true; const body = { first_name: document.getElementById('edit-fname').value, last_name: document.getElementById('edit-lname').value, aura_color: document.getElementById('edit-color').value }; try { const res = await fetch('/api/update_profile', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }); if(res.ok) { closeModal('info-confirm-modal'); closeModal('edit-info-modal'); loadData(); } } catch(e) { alert("Failed"); } btn.innerHTML = originalText; btn.disabled = false; }

// --- CALENDAR RENDERER ---
function renderCalendar() { 
    const g = document.getElementById('cal-grid'); 
    if (!g) return; 
    g.innerHTML = ''; 
    const m = currentCalendarDate.getMonth(); 
    const y = currentCalendarDate.getFullYear(); 

    document.getElementById('cal-month-year').innerText = new Date(y,m).toLocaleString('default',{month:'long', year:'numeric'}); 

    const now = new Date();
    const isCurrent = (now.getMonth() === m && now.getFullYear() === y);

    ["S","M","T","W","T","F","S"].forEach(d => g.innerHTML += `<div>${d}</div>`); 
    const days = new Date(y, m+1, 0).getDate(); 
    const f = new Date(y, m, 1).getDay(); 

    for(let i=0; i<f; i++) g.innerHTML += `<div></div>`; 

    for(let i=1; i<=days; i++) { 
        const d = document.createElement('div'); 
        d.className = 'cal-day'; 
        d.innerText = i; 
        if (isCurrent && i === now.getDate()) d.classList.add('today');

        const dateKey = `${y}-${String(m+1).padStart(2,'0')}-${String(i).padStart(2,'0')}`;
        // Find entry by date string
        const entry = Object.values(fullChatHistory).find(e => e.date === dateKey);
        
        if (entry) {
            d.classList.add('has-entry');
            d.onclick = (e) => { e.stopPropagation(); openArchive(entry.timestamp); };
        }
        g.appendChild(d); 
    } 
}

function changeMonth(d) { currentCalendarDate.setMonth(currentCalendarDate.getMonth() + d); renderCalendar(); }
function goToToday() { currentCalendarDate = new Date(); renderCalendar(); }