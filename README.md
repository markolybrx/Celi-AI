# Celi: Sovereign Mirror & Advisor

Celi is a high-level AI journal and strategic advisor built with Flask and the Gemini 2.5-Flash API. She uses a "Mirror Protocol" to provide brutally honest feedback and identify behavioral patterns.

## 🚀 Deployment (Render.com)
1. Link this repository to Render.
2. Set `Start Command` to: `gunicorn app:app`
3. Add `GEMINI_API_KEY` to Environment Variables.

## 🛠 Tech Stack
- **Backend:** Python (Flask)
- **AI:** Gemini (gemini 2.5-flash)
- **Frontend:** HTML5/TailwindCSS (Glassmorphism UI)
- **Storage:** Web File System Access API (Local `.json` vault)

## 🔒 Security
Celi uses a "Local-First" data architecture. Your journal entries are NEVER stored on the server. They live in a local `.json` file on your device that the browser "handshakes" with.
