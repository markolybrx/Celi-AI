// --- DATA & CALENDAR LOGIC ---

let pickerDate = new Date();
let selectedMonthIdx = 0;

async function loadData() { 
    try { 
        // 0. Show Loading State
        if(typeof loading === 'function') loading(true);

        // 1. FETCH USER DATA
        const userRes = await fetch('/api/get_user_data');
        if(userRes.status === 401) { window.location.href='/login'; return; }
        if(!userRes.ok) throw new Error("User Fetch Failed");
        const userData = await userRes.json();

        // 2. FETCH HISTORY DATA
        const histRes = await fetch('/api/get_history');
        const historyData = await histRes.json();

        // --- 3. POPULATE DASHBOARD ---
        
        // Greeting
        const hour = new Date().getHours(); 
        let timeGreet = hour >= 18 ? "Good Evening" : (hour >= 12 ? "Good Afternoon" : "Good Morning");
        updateText('greeting-text', `${timeGreet}, ${userData.username || 'Traveler'}!`); 

        // Rank Info
        updateText('rank-display', userData.rank || 'Novice Stargazer'); 
        updateText('rank-psyche', userData.star_type || 'Protostar'); // Mapped Star Type to Psyche
        
        // XP / Stardust
        const currentXp = userData.xp || 0;
        const nextXp = userData.next_level_xp || 100;
        const progressPercent = Math.min(100, (currentXp / nextXp) * 100);
        
        const bar = document.getElementById('rank-progress-bar');
        if(bar) bar.style.width = `${progressPercent}%`;
        
        updateText('stardust-cnt', `${userData.stardust || 0} Stardust`); 

        // --- 4. POPULATE PROFILE ---
        if (userData.profile_pic_id) {
            const pfpUrl = `/api/media/${userData.profile_pic_id}`;
            updateImage('pfp-img', pfpUrl);
            updateImage('profile-pfp-large', pfpUrl); 
        }

        // Set Mood Color based on Star Type (Heuristic)
        let themeColor = '#00f2fe';
        if(userData.star_type) {
            const t = userData.star_type.toLowerCase();
            if(t.includes('red')) themeColor = '#ff4757';
            else if(t.includes('gold') || t.includes('yellow')) themeColor = '#facc15';
            else if(t.includes('purple')) themeColor = '#a855f7';
            else if(t.includes('white')) themeColor = '#ffffff';
        }
        document.documentElement.style.setProperty('--mood', themeColor); 
        
        // Profile Modal Details
        updateText('profile-fullname', userData.username); 
        updateText('profile-id', userData.user_id ? userData.user_id.substring(0,8) : 'Unknown'); 
        updateText('profile-color-text', themeColor); 

        const dot = document.getElementById('profile-color-dot'); 
        if(dot) dot.style.backgroundColor = themeColor;

        // Edit Modal Pre-fill
        const editUid = document.getElementById('edit-uid-display');
        if(editUid) editUid.innerText = userData.username;

        // --- 5. PROCESS HISTORY FOR CALENDAR ---
        fullChatHistory = {}; // Reset global history object
        
        if (Array.isArray(historyData)) {
            historyData.forEach(entry => {
                // Fix Date Format: DB sends "YYYY-MM-DD HH:MM:SS", Calendar needs "YYYY-MM-DD"
                // We create a clean date key for the calendar map
                let dateKey = entry.date;
                if(dateKey.includes(' ')) dateKey = dateKey.split(' ')[0];
                
                // We assume _id is the key for fullChatHistory
                fullChatHistory[entry._id] = {
                    ...entry,
                    date: dateKey, // Ensure simplified date is available for calendar matching
                    full_date: entry.date
                };
            });
        }
        
        userHistoryDates = Object.values(fullChatHistory).map(e=>e.date);

        // --- 6. ECHO LOGIC ---
        // Get the most recent entry (historyData is sorted latest first from API)
        if (historyData.length > 0) {
            const lastEntry = historyData[0];
            let summary = lastEntry.summary || lastEntry.ai_response;
            if(summary.length > 60) summary = summary.substring(0, 60) + "...";
            
            updateText('echo-text', summary);
            updateText('echo-date', lastEntry.date);
        }

        // --- 7. RENDER ---
        renderCalendar(); 
        if(typeof loading === 'function') loading(false);

    } catch(e) { 
        console.error("Data Load Error:", e); 
        if(typeof loading === 'function') loading(false);
    } 
}

// --- UTILITY FUNCTIONS ---
async function handlePfpUpload() { const input = document.getElementById('pfp-upload-input'); if(input.files && input.files[0]) { const formData = new FormData(); formData.append('pfp', input.files[0]); const res = await fetch('/api/update_profile', { method: 'POST', body: formData }); const data = await res.json(); if(data.status === 'success') { loadData(); } } } // Updated to reuse loadData for refreshing image

function askUpdateInfo() { openModal('info-confirm-modal'); }

async function confirmUpdateInfo() { 
    const btn = document.getElementById('btn-confirm-info'); 
    const originalText = "Confirm"; 
    btn.innerHTML = '<span class="spinner"></span>'; btn.disabled = true; 
    
    // Adapted fields to match what app.py expects (username/bio)
    const body = new FormData();
    body.append('username', document.getElementById('edit-fname').value); // Using first name input as username update for now
    body.append('bio', document.getElementById('edit-lname').value);     // Using last name input as bio update for now
    
    try { 
        const res = await fetch('/api/update_profile', { method:'POST', body: body }); 
        const data = await res.json(); 
        if(data.status === 'success') { 
            closeModal('info-confirm-modal'); 
            closeModal('edit-info-modal'); 
            showStatus(true, "Profile Updated"); 
            loadData(); 
        } else { 
            showStatus(false, data.message || "Update Failed"); 
        } 
    } catch(e) { 
        showStatus(false, "Connection Failed"); 
    } 
    btn.innerHTML = originalText; btn.disabled = false; 
}

// Keep existing security functions, assuming endpoints might be added later
async function updateSecurity(type) { showStatus(false, "Security updates disabled in this version."); }
async function performWipe() { alert("History Wipe disabled for safety."); }

// --- CALENDAR RENDERER (PRESERVED) ---
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

    // 1. Build a Map of Date -> Entry Data
    const dateMap = {};
    Object.keys(fullChatHistory).forEach(id => {
        const entry = fullChatHistory[id];
        const dKey = entry.date; // This is now YYYY-MM-DD from our loadData fix

        // Logic: If multiple entries on same day, prioritize 'void' (rant) for indicator
        if (!dateMap[dKey] || entry.mode === 'void') {
            dateMap[dKey] = { id: id, mode: entry.mode || 'journal' };
        }
    });

    // Grid Headers
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

        // CHECK ENTRY & APPLY STYLE
        if (dateMap[dateKey]) {
            const entryData = dateMap[dateKey];

            // Differentiate Void vs Journal
            if (entryData.mode === 'void') {
                d.classList.add('has-void');
            } else {
                d.classList.add('has-entry');
            }

            // Click Handler
            d.onclick = (e) => {
                e.stopPropagation(); // Prevent bubbling issues
                // openArchive is assumed to be in chat.js
                if(typeof openArchive === 'function') openArchive(entryData.id);
            };
        }

        g.appendChild(d); 
    } 
}

function changeMonth(d) { currentCalendarDate.setMonth(currentCalendarDate.getMonth() + d); renderCalendar(); }
function goToToday() { currentCalendarDate = new Date(); renderCalendar(); }

// --- ADVANCED DATE PICKER LOGIC (PRESERVED) ---
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