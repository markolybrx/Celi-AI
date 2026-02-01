// --- CHAT & INTERACTION LOGIC ---

function getStarsHTML(rankTitle) { 
    let count = 0; 
    if (rankTitle.includes("VI")) count = 6; 
    else if (rankTitle.includes("IV")) count = 4; 
    else if (rankTitle.includes("V")) count = 5; 
    else if (rankTitle.includes("III")) count = 3; 
    else if (rankTitle.includes("II")) count = 2; 
    else if (rankTitle.includes("I")) count = 1; 
    
    if(rankTitle.includes("Ethereal") && count > 5) count = 5; 
    
    return Array(count).fill(STAR_SVG).join(''); 
}

function handleFileSelect() { 
    const input = document.getElementById('img-upload'); 
    if(input.files && input.files[0]) { 
        activeMediaFile = input.files[0]; 
        document.getElementById('chat-input').placeholder = "Image attached. Add context..."; 
    } 
}

function handleAudioSelect() { 
    const input = document.getElementById('audio-upload'); 
    if(input.files && input.files[0]) { 
        activeAudioFile = input.files[0]; 
        document.getElementById('chat-input').placeholder = "Audio attached. Transmitting..."; 
        sendMessage(); 
    } 
}

function toggleMic() { document.getElementById('audio-upload').click(); }

function parseMarkdown(text) {
    if (!text) return "";
    let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                   .replace(/\*(.*?)\*/g, '<em>$1</em>')
                   .replace(/\n/g, '<br>');
    return html;
}

function showTyping() { 
    document.getElementById('typing-indicator').classList.remove('hidden'); 
    document.getElementById('chat-history').scrollTop = 9999; 
}

function hideTyping() { 
    document.getElementById('typing-indicator').classList.add('hidden'); 
}

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
    const div = document.createElement('div'); 
    div.className = `msg msg-${sender}`; 
    div.innerHTML = parseMarkdown(txt); 
    
    if (sender === 'ai') {
        const btn = document.createElement('span'); 
        btn.className = 'voice-play-btn'; 
        btn.innerHTML = ICON_SPEAK;
        const cleanText = txt.replace(/\*\*/g, '').replace(/\*/g, '');
        btn.onclick = () => speakText(cleanText); 
        div.appendChild(btn);
    }
    
    const history = document.getElementById('chat-history'); 
    const indicator = document.getElementById('typing-indicator');
    history.insertBefore(div, indicator); 
    history.scrollTop = 9999; 
}

// --- SOUL SYNTHESIS / ARCHIVE LOGIC (V12.13 UPDATED) ---
function openArchive(id) { 
    const modal = document.getElementById('archive-modal'); 
    modal.classList.add('active'); 
    modal.style.display = 'flex'; // Ensure flex display for centering

    // Reset fields
    document.getElementById('archive-date').innerText = "Loading...";
    document.getElementById('archive-analysis').innerText = "Loading synthesis...";
    document.getElementById('archive-image-container').classList.add('hidden');
    document.getElementById('archive-audio-container').classList.add('hidden');

    // Fetch details for this specific entry ID
    fetch('/api/star_detail', { 
        method:'POST', 
        headers:{'Content-Type':'application/json'}, 
        body:JSON.stringify({id})
    })
    .then(r => r.json())
    .then(d => { 
        document.getElementById('archive-date').innerText = d.date; 
        // Use summary or analysis, whichever exists
        document.getElementById('archive-analysis').innerText = d.analysis || d.summary || "No synthesis available for this entry."; 
        
        // Handle Image
        const imgContainer = document.getElementById('archive-image-container'); 
        if(d.image_url) { 
            imgContainer.classList.remove('hidden'); 
            document.getElementById('archive-image').src = d.image_url; 
        } 
        
        // Handle Audio
        const audioContainer = document.getElementById('archive-audio-container'); 
        const audioEl = document.getElementById('archive-audio'); 
        if(d.audio_url) { 
            audioContainer.classList.remove('hidden'); 
            audioEl.src = d.audio_url; 
        } 
    })
    .catch(e => {
        document.getElementById('archive-analysis').innerText = "Error retrieving archive data.";
        console.error(e);
    });
}

function openChat(mode) { 
    currentMode = mode; 
    if(typeof SonicAtmosphere !== 'undefined') SonicAtmosphere.playMode(mode); 
    
    document.getElementById('chat-overlay').classList.add('active'); 
    const w = document.getElementById('chat-modal-window'); 
    w.className = `chat-window origin-${mode === 'rant' ? 'void' : 'ai'}`; 
    document.getElementById('chat-header-title').innerText = mode === 'rant' ? "THE VOID" : "CELI AI"; 
    renderChatHistory(fullChatHistory); 
}

function closeChat() { 
    document.getElementById('chat-overlay').classList.remove('active'); 
    if(typeof SonicAtmosphere !== 'undefined') SonicAtmosphere.playMode('journal'); 
}

function closeArchive() { 
    const modal = document.getElementById('archive-modal');
    modal.classList.remove('active'); 
    modal.style.display = 'none'; // Hide completely
    
    const audio = document.getElementById('archive-audio');
    if(audio) audio.pause(); 
}

function spawnStardust() { 
    const s = document.getElementById('nav-pfp').getBoundingClientRect(); 
    const t = document.getElementById('rank-progress-bar').getBoundingClientRect(); 
    const pfp = document.getElementById('nav-pfp'); 
    
    pfp.classList.remove('pulse-anim'); 
    void pfp.offsetWidth; 
    pfp.classList.add('pulse-anim'); 
    
    for(let i=0; i<8; i++){ 
        setTimeout(()=>{ 
            const p = document.createElement('div'); 
            p.className='stardust-particle'; 
            p.style.left = (s.left+s.width/2)+'px'; 
            p.style.top = (s.top+s.height/2)+'px'; 
            document.body.appendChild(p); 
            
            const tx = t.left+Math.random()*t.width; 
            const ty = t.top+t.height/2; 
            
            p.animate([
                {transform:'translate(0,0) scale(1)', opacity:1},
                {transform:`translate(${tx-parseFloat(p.style.left)}px, ${ty-parseFloat(p.style.top)}px) scale(0.5)`, opacity:0}
            ], {
                duration: 800+Math.random()*400, 
                easing:'cubic-bezier(0.25,1,0.5,1)'
            }).onfinish = () => p.remove(); 
        }, i*100); 
    } 
}

function renderChatHistory(h) { 
    const c = document.getElementById('chat-history'); 
    Array.from(c.children).forEach(child => { 
        if(child.id !== 'typing-indicator') c.removeChild(child); 
    });
    
    Object.keys(h).sort().slice(-50).forEach(k => { 
        appendMsg(h[k].summary || "Entry", 'user'); 
        appendMsg(h[k].reply, 'ai'); 
    }); 
}
