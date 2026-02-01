const canvas = document.getElementById('starfield'); const ctx = canvas.getContext('2d'); 
let animationFrameId; let isGalaxyActive = false; 
let galaxyData = []; let ambientStars = []; 

function resizeStars() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; } 
window.addEventListener('resize', resizeStars); resizeStars();

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

canvas.addEventListener('click', (e) => { 
    if(!isGalaxyActive) return; 
    const rect = canvas.getBoundingClientRect(); 
    const x = e.clientX - rect.left; 
    const y = e.clientY - rect.top; 
    galaxyData.forEach(star => { if(Math.hypot(x-star.x, y-star.y) < 20) openArchive(star.id); }); 
});

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
