// --- DATA & CALENDAR LOGIC ---

let pickerDate = new Date();
let selectedMonthIdx = 0;

async function loadData() { 
    try { 
        const res = await fetch('/api/data'); 
        if(!res.ok) return; 
        
        const data = await res.json(); 
        if(data.status === 'guest') { window.location.href='/login'; return; } 

        // --- 1. LOAD DASHBOARD DATA ---
        if (data.progression_tree) {
            globalRankTree = data.progression_tree; 
            currentLockIcon = data.progression_tree.lock_icon || '';
        }

        const hour = new Date().getHours(); 
        let timeGreet = hour >= 18 ? "Good Evening" : (hour >= 12 ? "Good Afternoon" : "Good Morning");
        
        const safeSet = (id, val) => { const el = document.getElementById(id); if(el) el.innerText = val; };
        const safeSrc = (id, val) => { const el = document.getElementById(id); if(el) el.src = val || ''; };

        safeSet('greeting-text', `${timeGreet}, ${data.first_name || 'Traveler'}!`); 
        safeSet('rank-display', data.rank || 'Observer III'); 
        safeSet('rank-psyche', data.rank_psyche || 'The Telescope'); 
        safeSet('stardust-cnt', `${data.stardust_current || 0}/${data.stardust_max || 100} Stardust`); 
        
        const progressBar = document.getElementById('rank-progress-bar');
        if(progressBar) progressBar.style.width = `${data.rank_progress || 0}%`; 

        // --- 2. LOAD PROFILE DATA ---
        safeSrc('pfp-img', data.profile_pic); 
        safeSrc('profile-pfp-large', data.profile_pic); 
        
        document.documentElement.style.setProperty('--mood', data.current_color || '#00f2fe'); 
        
        const rankIcon = document.getElementById('main-rank-icon');
        if(rankIcon && data.current_svg) rankIcon.innerHTML = data.current_svg; 

        safeSet('profile-fullname', `${data.first_name} ${data.last_name}`); 
        safeSet('profile-id', data.username); 
        safeSet('profile-color-text', data.aura_color); 

        const dot = document.getElementById('profile-color-dot'); 
        if(dot) {
            dot.style.backgroundColor = data.aura_color || data.current_color || '#00f2fe';
        }

        safeSet('profile-secret-q', SQ_MAP[data.secret_question] || data.secret_question);
        
        const editFname = document.getElementById('edit-fname'); if(editFname) editFname.value = data.first_name || '';
        const editLname = document.getElementById('edit-lname'); if(editLname) editLname.value = data.last_name || '';
        const editColor = document.getElementById('edit-color'); if(editColor) editColor.value = data.aura_color || '#00f2fe';
        safeSet('edit-uid-display', data.username);
        
        const themeBtn = document.getElementById('theme-btn');
        if(themeBtn) themeBtn.innerText = document.documentElement.getAttribute('data-theme') === 'light' ? 'Light' : 'Dark';

        // --- 3. PREPARE HISTORY (LIGHTWEIGHT) ---
        if(data.history) fullChatHistory = data.history; 
        else fullChatHistory = {};
        
        userHistoryDates = Object.values(fullChatHistory).map(e=>e.date);

        // --- 4. WEEKLY INSIGHT (REPLACES ECHO) ---
        const insightText = document.getElementById('insight-text');
        const insightRecBox = document.getElementById('insight-rec-box');
        const insightRecText = document.getElementById('insight-rec-text');
        const insightAction = document.getElementById('insight-action');
        const insightStatus = document.getElementById('insight-status');

        if (insightText) {
            const insight = data.weekly_insight;

            if (insight) {
                insightText.innerText = `"${insight.text}"`;
                if(insightRecText) insightRecText.innerText = insight.recommendation;
                
                // State B: Active
                if (insight.status === 'active') {
                    if(insightRecBox) insightRecBox.classList.remove('hidden');
                    if(insightAction) insightAction.classList.add('hidden');
                    if(insightStatus) {
                        insightStatus.innerText = "Weekly Pattern";
                        insightStatus.className = "text-xs text-indigo-300 bg-indigo-900/30 px-2 py-1 rounded-md";
                    }
                } 
                // State A: Empty/Persuasion
                else {
                    if(insightRecBox) insightRecBox.classList.add('hidden');
                    if(insightAction) insightAction.classList.remove('hidden');
                    if(insightStatus) insightStatus.innerText = "Awaiting Data";
                }
            } else {
                // Fallback (Very first login)
                insightText.innerText = `"I am calibrated and ready. Your journey begins with a single word."`;
                if(insightRecBox) insightRecBox.classList.add('hidden');
            }
        }

        // --- 5. INFINITE TRIVIA LOGIC ---
        const triviaText = document.getElementById('daily-trivia-text');
        
        if (triviaText && data.daily_trivia) {
            triviaText.innerText = `"${data.daily_trivia.fact}"`;
            
            // Visual loading state check
            if(data.daily_trivia.loading) {
                triviaText.classList.add('animate-pulse');
                triviaText.style.opacity = "0.7";
            } else {
                triviaText.classList.remove('animate-pulse');
                triviaText.style.opacity = "1";
            }
        }

        // --- 6. RENDER CALENDAR ---
        renderCalendar(); 
        
    } catch(e) { 
        console.error("CRITICAL DATA ERROR:", e); 
    } 
}

// --- UTILITY FUNCTIONS ---
async function handlePfpUpload() { const input = document.getElementById('pfp-upload-input'); if(input.files && input.files[0]) { const formData = new FormData(); formData.append('pfp', input.files[0]); const res = await fetch('/api/update_pfp', { method: 'POST', body: formData }); const data = await res.json(); if(data.status === 'success') { document.getElementById('pfp-img').src = data.url; document.getElementById('profile-pfp-large').src = data.url; } } }
function askUpdateInfo() { openModal('info-confirm-modal'); }
async function confirmUpdateInfo() { const btn = document.getElementById('btn-confirm-info'); const originalText = "Confirm"; btn.innerHTML = '<span class="spinner"></span>'; btn.disabled = true; const body = { first_name: document.getElementById('edit-fname').value, last_name: document.getElementById('edit-lname').value, aura_color: document.getElementById('edit-color').value }; try { const res = await fetch('/api/update_profile', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }); const data = await res.json(); if(data.status === 'success') { closeModal('info-confirm-modal'); closeModal('edit-info-modal'); showStatus(true, "Profile Updated"); loadData(); } else { showStatus(false, data.message); } } catch(e) { showStatus(false, "Connection Failed"); } btn.innerHTML = originalText; btn.disabled = false; }
async function updateSecurity(type) { let body = {}; const btn = type === 'pass' ? document.getElementById('btn-update-pass') : document.getElementById('btn-update-secret'); const originalText = "Update"; btn.innerHTML = '<span class="spinner"></span> Loading...'; btn.disabled = true; if(type === 'pass') { const p1 = document.getElementById('new-pass-input').value; const p2 = document.getElementById('confirm-pass-input').value; if(p1 !== p2) { document.getElementById('new-pass-input').classList.add('input-error'); document.getElementById('confirm-pass-input').classList.add('input-error'); setTimeout(()=>{ document.getElementById('new-pass-input').classList.remove('input-error'); document.getElementById('confirm-pass-input').classList.remove('input-error'); }, 500); btn.innerHTML=originalText; btn.disabled=false; return; } body = { new_password: p1 }; } else { const q = document.getElementById('new-secret-q').value; if(!q) { showStatus(false, "Select a Question"); btn.innerHTML=originalText; btn.disabled=false; return; } body = { new_secret_q: q, new_secret_a: document.getElementById('new-secret-a').value }; } try { const res = await fetch('/api/update_security', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }); const data = await res.json(); if(data.status === 'success') { closeModal('change-pass-modal'); closeModal('change-secret-modal'); showStatus(true, "Security details updated."); loadData(); } else { showStatus(false, data.message); } } catch(e) { showStatus(false, "Connection Failed"); } btn.innerHTML = originalText; btn.disabled = false; }
async function performWipe() { const btn = document.querySelector('#delete-confirm-modal button.bg-red-500'); const originalText = btn.innerText; btn.innerText = "Deleting..."; btn.disabled = true; try { const res = await fetch('/api/clear_history', { method: 'POST' }); const data = await res.json(); if (data.status === 'success') { window.location.href = '/login'; } else { alert("Error: " + data.message); btn.innerText = originalText; btn.disabled = false; } } catch (e) { alert("Connection failed."); btn.innerText = originalText; btn.disabled = false; } }

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
    const todayBtn = document.getElementById('cal-today-btn');
    if (todayBtn) {
        if (!isCurrent) todayBtn.classList.remove('hidden');
        else todayBtn.classList.add('hidden');
    }

    const dateMap = {};
    if (fullChatHistory) {
        Object.keys(fullChatHistory).forEach(id => {
            const entry = fullChatHistory[id];
            if (entry && entry.date) { 
                const dKey = entry.date;
                if (!dateMap[dKey] || entry.mode === 'rant') {
                    dateMap[dKey] = { id: id, mode: entry.mode || 'journal' };
                }
            }
        });
    }

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

        if (dateMap[dateKey]) {
            const entryData = dateMap[dateKey];
            if (entryData.mode === 'rant') {
                d.classList.add('has-void');
            } else {
                d.classList.add('has-entry');
            }
            d.onclick = (e) => {
                e.stopPropagation(); 
                openArchive(entryData.id);
            };
        }
        g.appendChild(d); 
    } 
}

function changeMonth(d) { currentCalendarDate.setMonth(currentCalendarDate.getMonth() + d); renderCalendar(); }
function goToToday() { currentCalendarDate = new Date(); renderCalendar(); }

// --- ADVANCED DATE PICKER LOGIC ---
let isYearMode = false;

function toggleDatePicker() {
    const picker = document.getElementById('cal-picker');
    if (!picker) return;
    const isActive = picker.classList.contains('active');

    if (!isActive) {
        pickerDate = new Date(currentCalendarDate.getTime());
        selectedMonthIdx = pickerDate.getMonth();
        isYearMode = false; 
        renderPickerUI();
        picker.classList.add('active');
    } else {
        picker.classList.remove('active');
    }
}

function toggleYearMode() {
    isYearMode = !isYearMode;
    renderPickerUI();
}

function renderPickerUI() {
    const yearText = document.getElementById('picker-year-text');
    const monthsContainer = document.getElementById('picker-months-container');
    const yearsContainer = document.getElementById('picker-years-container');

    yearText.innerText = pickerDate.getFullYear();

    if (isYearMode) {
        monthsContainer.classList.add('hidden');
        yearsContainer.classList.remove('hidden');
        yearsContainer.innerHTML = '';

        const currentYear = new Date().getFullYear();
        const startYear = currentYear - 15;
        const endYear = currentYear + 15;

        for (let y = startYear; y <= endYear; y++) {
            const btn = document.createElement('div');
            btn.className = `picker-year-btn ${y === pickerDate.getFullYear() ? 'selected' : ''}`;
            btn.innerText = y;
            btn.onclick = () => {
                pickerDate.setFullYear(y);
                toggleYearMode(); 
            };
            yearsContainer.appendChild(btn);
        }
        setTimeout(() => {
            const selected = yearsContainer.querySelector('.selected');
            if(selected) selected.scrollIntoView({block: 'center'});
        }, 10);

    } else {
        yearsContainer.classList.add('hidden');
        monthsContainer.classList.remove('hidden');
        monthsContainer.innerHTML = '';

        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        months.forEach((m, idx) => {
            const btn = document.createElement('div');
            btn.className = `picker-month-btn ${idx === selectedMonthIdx ? 'selected' : ''}`;
            btn.innerText = m;
            btn.onclick = () => {
                selectedMonthIdx = idx;
                pickerDate.setMonth(idx);
                renderPickerUI();
            };
            monthsContainer.appendChild(btn);
        });
    }
}

function confirmDateSelection() {
    currentCalendarDate.setFullYear(pickerDate.getFullYear());
    currentCalendarDate.setMonth(selectedMonthIdx);
    renderCalendar();
    toggleDatePicker(); 
}
