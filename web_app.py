"""
ARKAINBRAIN — AI-Powered Gaming Intelligence Platform
by ArkainGames.com
"""
import json, os, secrets, sqlite3, subprocess, time, uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"  # Disable tracing prompt
os.environ["DO_NOT_TRACK"] = "1"
os.environ["CREWAI_STORAGE_DIR"] = "/tmp/crewai_storage"

# ── Pre-create CrewAI config to prevent interactive tracing prompt ──
for _d in [Path.home() / ".crewai", Path("/tmp/crewai_storage")]:
    _d.mkdir(parents=True, exist_ok=True)
    _cfg = _d / "config.json"
    if not _cfg.exists():
        _cfg.write_text(json.dumps({"tracing_enabled": False, "tracing_disabled": True}))

from flask import Flask, redirect, url_for, session, request, jsonify, send_from_directory, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # Trust Railway's reverse proxy
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["PREFERRED_URL_SCHEME"] = "https"

LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", "arkainbrain.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")     # Concurrent reads + writes
    conn.execute("PRAGMA busy_timeout=5000")     # Wait up to 5s for lock
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, picture TEXT, created_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, job_type TEXT NOT NULL DEFAULT 'slot_pipeline', title TEXT NOT NULL, params TEXT, status TEXT DEFAULT 'queued', current_stage TEXT DEFAULT 'Initializing', output_dir TEXT, error TEXT, created_at TEXT DEFAULT (datetime('now')), completed_at TEXT, FOREIGN KEY (user_id) REFERENCES users(id));
        CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
    """)
    db.close()
init_db()

live_jobs = {}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session: return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def current_user(): return session.get("user", {})

BRAND_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg-void:#08080c;--bg-surface:#0e0e14;--bg-card:#13131b;--bg-card-hover:#1a1a25;--bg-input:#0b0b10;--border:#1e1e2e;--text:#c8cdd5;--text-bright:#eef1f6;--text-muted:#5a5f72;--accent:#00f0ff;--accent-dim:#00f0ff22;--accent2:#8b5cf6;--success:#22c55e;--warning:#f59e0b;--danger:#ef4444;--glow:0 0 30px #00f0ff15,0 0 60px #00f0ff08}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Sora',sans-serif;background:var(--bg-void);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}
body::before{content:'';position:fixed;inset:0;z-index:9999;pointer-events:none;opacity:0.025;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
.topbar{position:sticky;top:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:0 32px;height:56px;background:var(--bg-surface);border-bottom:1px solid var(--border);backdrop-filter:blur(12px)}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:17px;letter-spacing:-0.5px;color:var(--text-bright);text-decoration:none}
.logo-mark{width:28px;height:28px;border-radius:7px;background:linear-gradient(135deg,#00f0ff,#8b5cf6);display:grid;place-items:center;font-size:14px;font-weight:800;color:#000}
.user-pill{display:flex;align-items:center;gap:8px;padding:4px 12px 4px 4px;border-radius:20px;background:var(--bg-card);border:1px solid var(--border);font-size:12px;color:var(--text-muted);text-decoration:none}
.user-pill img{width:26px;height:26px;border-radius:50%}
.user-pill:hover{border-color:var(--accent);color:var(--text)}
.shell{display:grid;grid-template-columns:220px 1fr;min-height:calc(100vh - 56px)}
.sidebar{padding:20px 0;border-right:1px solid var(--border);background:var(--bg-surface)}
.sidebar a{display:flex;align-items:center;gap:10px;padding:10px 24px;font-size:13px;font-weight:500;color:var(--text-muted);text-decoration:none;transition:all 0.15s}
.sidebar a:hover,.sidebar a.active{color:var(--text-bright);background:var(--accent-dim);border-right:2px solid var(--accent)}
.sidebar a svg{width:16px;height:16px;opacity:0.6}
.sidebar .section-label{font-size:10px;font-weight:700;letter-spacing:1.5px;color:var(--text-muted);padding:20px 24px 6px;text-transform:uppercase}
.main{padding:32px 40px;max-width:1100px}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px;transition:border-color 0.2s}
.card:hover{border-color:#2a2a3e}
.card h2{font-size:15px;font-weight:700;color:var(--text-bright);margin-bottom:16px;display:flex;align-items:center;gap:8px}
label{display:block;font-size:11px;font-weight:600;color:var(--text-muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:0.8px}
input,select,textarea{width:100%;padding:10px 14px;border-radius:8px;border:1px solid var(--border);background:var(--bg-input);color:var(--text-bright);font-family:'Sora',sans-serif;font-size:13px;margin-bottom:16px;outline:none;transition:border-color 0.2s}
input:focus,select:focus,textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}
textarea{min-height:70px;resize:vertical}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 24px;border-radius:8px;border:none;font-family:'Sora',sans-serif;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s;text-decoration:none}
.btn-primary{background:linear-gradient(135deg,#00f0ff,#00c4d4);color:#000;box-shadow:var(--glow)}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 0 40px #00f0ff30}
.btn-ghost{background:transparent;color:var(--text);border:1px solid var(--border)}
.btn-ghost:hover{border-color:var(--accent);color:var(--accent)}
.btn-sm{padding:7px 14px;font-size:12px}
.btn-full{width:100%}
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600}
.badge-running{background:#00f0ff18;color:var(--accent)}
.badge-complete{background:#22c55e18;color:var(--success)}
.badge-failed{background:#ef444418;color:var(--danger)}
.badge-queued{background:#f59e0b18;color:var(--warning)}
.badge-running::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--accent);animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
.history-item{display:grid;grid-template-columns:1fr 120px 140px 100px;align-items:center;padding:14px 16px;border-bottom:1px solid var(--border);font-size:13px;transition:background 0.15s}
.history-item:hover{background:var(--bg-card-hover)}
.history-title{font-weight:600;color:var(--text-bright)}
.history-type{color:var(--text-muted);font-size:11px;font-weight:500}
.history-date{color:var(--text-muted);font-size:12px}
.history-actions{display:flex;gap:6px;justify-content:flex-end}
.file-row{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px;transition:background 0.15s}
.file-row:hover{background:var(--bg-card-hover)}
.file-row a{color:var(--accent);text-decoration:none;font-family:'JetBrains Mono',monospace;font-size:12px}
.file-row a:hover{text-decoration:underline}
.file-size{color:var(--text-muted);font-size:11px;font-family:'JetBrains Mono',monospace}
.login-wrap{min-height:100vh;display:grid;place-items:center;background:radial-gradient(ellipse at 30% 20%,#0a1628 0%,var(--bg-void) 70%)}
.login-box{text-align:center;padding:48px;width:420px;background:var(--bg-card);border:1px solid var(--border);border-radius:16px;box-shadow:var(--glow)}
.login-box h1{font-size:28px;font-weight:800;letter-spacing:-1px;color:var(--text-bright);margin:20px 0 8px}
.login-box p{color:var(--text-muted);font-size:13px;margin-bottom:32px;line-height:1.6}
.google-btn{display:inline-flex;align-items:center;gap:10px;padding:12px 32px;border-radius:8px;border:1px solid var(--border);background:var(--bg-surface);color:var(--text-bright);font-family:'Sora',sans-serif;font-size:14px;font-weight:600;cursor:pointer;transition:all 0.2s;text-decoration:none}
.google-btn:hover{border-color:var(--accent);background:var(--accent-dim);box-shadow:0 0 30px #00f0ff10}
.google-btn svg{width:18px;height:18px}
.recon-input-group{display:flex;gap:12px;align-items:flex-end}
.recon-input-group input{margin-bottom:0;flex:1}
.recon-input-group .btn{white-space:nowrap;height:40px}
.empty-state{text-align:center;padding:60px 20px;color:var(--text-muted)}
.empty-state h3{font-size:16px;color:var(--text);margin-bottom:6px}
.empty-state p{font-size:13px}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
.stat-card{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:16px;text-align:center}
.stat-card .stat-icon{font-size:22px;margin-bottom:6px}
.stat-card .stat-val{font-size:20px;font-weight:800;color:var(--text-bright)}
.stat-card .stat-label{font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-top:2px}
.stat-card.online{border-color:#22c55e33}
.stat-card.offline{border-color:#ef444433;opacity:0.6}
.feature-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px 16px}
.feature-grid label{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:500;color:var(--text);text-transform:none;margin-bottom:8px;cursor:pointer;padding:8px 12px;border-radius:8px;transition:background 0.15s;border:1px solid transparent}
.feature-grid label:hover{background:var(--bg-card-hover);border-color:var(--border)}
.feature-grid label input{width:auto;margin:0}
.feature-grid .feat-tag{font-size:9px;padding:2px 6px;border-radius:4px;font-weight:700;margin-left:auto}
.feat-tag.ip-risk{background:#ef444422;color:var(--danger)}
.feat-tag.safe{background:#22c55e22;color:var(--success)}
.feat-tag.banned{background:#f59e0b22;color:var(--warning)}
.toggle-section{padding:16px;background:var(--bg-input);border-radius:8px;margin-top:12px;display:flex;flex-wrap:wrap;gap:20px}
.toggle-item{display:flex;align-items:center;gap:8px}
.toggle-item input{width:auto;margin:0}
.toggle-item label{margin:0;font-size:12px;text-transform:none;color:var(--text-bright);font-weight:600}
.toggle-item .toggle-desc{font-size:11px;color:var(--text-muted)}
.proto-frame{width:100%;height:600px;border:1px solid var(--border);border-radius:8px;background:#000}
.audio-player{display:flex;align-items:center;gap:12px;padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px}
.audio-player audio{height:32px;flex:1}
.audio-player .audio-name{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent);min-width:140px}
.cert-timeline{display:flex;gap:0;margin:16px 0}
.cert-step{flex:1;text-align:center;padding:12px 8px;position:relative}
.cert-step::after{content:'';position:absolute;top:26px;right:0;width:50%;height:2px;background:var(--border)}
.cert-step::before{content:'';position:absolute;top:26px;left:0;width:50%;height:2px;background:var(--border)}
.cert-step:first-child::before,.cert-step:last-child::after{display:none}
.cert-step .cert-dot{width:12px;height:12px;border-radius:50%;background:var(--accent);margin:0 auto 8px;position:relative;z-index:1}
.cert-step .cert-title{font-size:11px;font-weight:700;color:var(--text-bright)}
.cert-step .cert-sub{font-size:10px;color:var(--text-muted)}
@media(max-width:768px){.shell{grid-template-columns:1fr}.sidebar{display:none}.main{padding:20px}.history-item{grid-template-columns:1fr 1fr;gap:8px}.stat-grid{grid-template-columns:repeat(2,1fr)}.feature-grid{grid-template-columns:1fr 1fr}}
"""

ICON_DASH = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/></svg>'
ICON_PLUS = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>'
ICON_SEARCH = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>'
ICON_FOLDER = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>'
ICON_CLOCK = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
ICON_GLOBE = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
ICON_DB = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/></svg>'
ICON_REVIEW = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
ICON_SETTINGS = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>'
GOOGLE_SVG = '<svg viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>'

def layout(content, page="dashboard"):
    user = current_user()
    items = [("dashboard","Dashboard",ICON_DASH,"/"),("new","New Pipeline",ICON_PLUS,"/new"),("recon","State Recon",ICON_GLOBE,"/recon"),("reviews","Reviews",ICON_REVIEW,"/reviews"),("history","History",ICON_CLOCK,"/history"),("files","All Files",ICON_FOLDER,"/files"),("qdrant","Qdrant Status",ICON_DB,"/qdrant"),("settings","Settings",ICON_SETTINGS,"/settings")]
    nav = '<div class="section-label">Platform</div>'
    for k,l,i,h in items:
        nav += f'<a href="{h}" class="{"active" if page==k else ""}">{i} {l}</a>'
    pic = user.get("picture","")
    name = user.get("name","User")
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ARKAINBRAIN</title><style>{BRAND_CSS}</style></head><body>
<div class="topbar"><a href="/" class="logo"><div class="logo-mark">A</div>ARKAINBRAIN</a><a href="/logout" class="user-pill"><img src="{pic}" alt="" onerror="this.style.display='none'">{name} &middot; Sign Out</a></div>
<div class="shell"><nav class="sidebar">{nav}<div class="section-label" style="margin-top:auto;padding-top:40px"><span style="opacity:0.4">ArkainGames.com</span></div></nav><main class="main">{content}</main></div></body></html>'''

# ─── AUTH ───
@app.route("/login")
def login_page():
    return f'''<!DOCTYPE html><html><head><title>ARKAINBRAIN</title><style>{BRAND_CSS}</style></head><body>
<div class="login-wrap"><div class="login-box"><div class="logo-mark" style="width:48px;height:48px;font-size:22px;margin:0 auto;border-radius:12px">A</div><h1>ARKAINBRAIN</h1><p>AI-powered gaming intelligence platform.<br>Built by ArkainGames.com</p><a href="/auth/google" class="google-btn">{GOOGLE_SVG} Continue with Google</a></div></div></body></html>'''

@app.route("/auth/google")
def google_login():
    return google.authorize_redirect(url_for("google_callback", _external=True))

@app.route("/auth/callback")
def google_callback():
    try:
        token = google.authorize_access_token()
        info = token.get("userinfo") or google.userinfo()
        db = get_db()
        db.execute("INSERT INTO users (id,email,name,picture) VALUES (?,?,?,?) ON CONFLICT(email) DO UPDATE SET name=excluded.name,picture=excluded.picture",
            (str(uuid.uuid4()), info["email"], info.get("name",""), info.get("picture","")))
        db.commit()
        row = db.execute("SELECT * FROM users WHERE email=?", (info["email"],)).fetchone()
        db.close()
        session["user"] = {"id":row["id"],"email":row["email"],"name":row["name"],"picture":row["picture"]}
        return redirect("/")
    except Exception as e:
        return f"Auth error: {e}", 500

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

# ─── DASHBOARD ───
@app.route("/")
@login_required
def dashboard():
    user = current_user()
    db = get_db()
    recent = db.execute("SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 8", (user["id"],)).fetchall()
    db.close()
    rows = ""
    for job in recent:
        jid = job["id"]
        status = live_jobs.get(jid,{}).get("status",job["status"])
        stage = live_jobs.get(jid,{}).get("current_stage",job["current_stage"] or "")
        bc = {"running":"badge-running","complete":"badge-complete","failed":"badge-failed"}.get(status,"badge-queued")
        tl = "Slot Pipeline" if job["job_type"]=="slot_pipeline" else "State Recon"
        dt = job["created_at"][:16].replace("T"," ") if job["created_at"] else ""
        act = f'<a href="/job/{jid}/files" class="btn btn-ghost btn-sm">Files</a>' if status=="complete" and job["output_dir"] else (f'<a href="/job/{jid}/logs" class="btn btn-ghost btn-sm" style="border-color:var(--accent);color:var(--accent)">Watch Live</a>' if status=="running" else "")
        rows += f'<div class="history-item"><div><div class="history-title">{job["title"]}</div><div class="history-type">{tl}</div></div><div><span class="badge {bc}">{status}</span></div><div class="history-date">{dt}</div><div class="history-actions">{act}</div></div>'
    if not rows:
        rows = '<div class="empty-state"><h3>No pipelines yet</h3><p>Launch a Slot Pipeline or State Recon to get started.</p></div>'
    fname = user.get("name","").split()[0] if user.get("name") else "Operator"
    # Check for pending reviews
    review_banner = ""
    try:
        from tools.web_hitl import get_pending_reviews
        pending = get_pending_reviews()
        if pending:
            review_banner = f'<a href="/reviews" class="card" style="border-color:var(--accent);background:var(--accent-dim);margin-bottom:20px;display:flex;align-items:center;gap:12px;text-decoration:none"><span class="badge badge-running" style="font-size:14px;padding:6px 14px">{len(pending)}</span><div><div style="font-weight:700;color:var(--text-bright);font-size:14px">Pipeline waiting for your review</div><div style="font-size:12px;color:var(--text-muted)">Click to approve, reject, or give feedback</div></div></a>'
    except Exception:
        pass

    # API status checks
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_serper = bool(os.getenv("SERPER_API_KEY"))
    has_elevenlabs = bool(os.getenv("ELEVENLABS_API_KEY"))
    has_qdrant = bool(os.getenv("QDRANT_URL"))

    api_cards = f'''<div class="stat-grid">
        <div class="stat-card {'online' if has_openai else 'offline'}"><div class="stat-icon">🧠</div><div class="stat-val">{'●' if has_openai else '○'}</div><div class="stat-label">OpenAI GPT-4o</div></div>
        <div class="stat-card {'online' if has_serper else 'offline'}"><div class="stat-icon">🔍</div><div class="stat-val">{'●' if has_serper else '○'}</div><div class="stat-label">Serper Search</div></div>
        <div class="stat-card {'online' if has_elevenlabs else 'offline'}"><div class="stat-icon">🔊</div><div class="stat-val">{'●' if has_elevenlabs else '○'}</div><div class="stat-label">ElevenLabs Audio</div></div>
        <div class="stat-card {'online' if has_qdrant else 'offline'}"><div class="stat-icon">🗃️</div><div class="stat-val">{'●' if has_qdrant else '○'}</div><div class="stat-label">Qdrant Vector DB</div></div>
    </div>'''

    # Count totals
    db2 = get_db()
    total_jobs = db2.execute("SELECT COUNT(*) FROM jobs WHERE user_id=?", (user["id"],)).fetchone()[0]
    completed_jobs = db2.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='complete'", (user["id"],)).fetchone()[0]
    db2.close()

    return layout(f'''
    <h2 style="font-size:22px;font-weight:800;color:var(--text-bright);margin-bottom:4px">Welcome back, {fname}</h2>
    <p style="color:var(--text-muted);font-size:13px;margin-bottom:20px">ARKAINBRAIN v4.0 — Pipeline Intelligence Dashboard</p>
    {review_banner}
    {api_cards}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
        <a href="/new" class="btn btn-primary btn-full" style="padding:16px">{ICON_PLUS} New Slot Pipeline</a>
        <a href="/recon" class="btn btn-ghost btn-full" style="padding:16px">{ICON_GLOBE} State Recon</a>
    </div>
    <div class="card"><h2>Intelligence Upgrades — Active</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px">
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">🛰️ <b>Pre-Flight Intel</b> — trend radar, jurisdiction scan, patent check</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">🔬 <b>Vision QA</b> — GPT-4o checks every generated image</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">📐 <b>Math Optimizer</b> — iterative RTP convergence ±0.1%</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">🎭 <b>Agent Debate</b> — designer vs mathematician negotiation</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">👤 <b>Player Behavior</b> — 5K session simulation, churn risk</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">🔒 <b>Patent Scanner</b> — IP conflict detection before design</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">🎮 <b>HTML5 Prototype</b> — playable browser demo auto-generated</div>
            <div style="padding:8px;border-radius:6px;background:{'var(--bg-input)' if has_elevenlabs else '#1a1010'}">{'🔊' if has_elevenlabs else '🔇'} <b>AI Sound Design</b> — {'ElevenLabs connected' if has_elevenlabs else '<a href="/settings" style="color:var(--danger)">Add API key</a>'}</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">📋 <b>Cert Planner</b> — test lab, timeline, cost mapping</div>
            <div style="padding:8px;border-radius:6px;background:var(--bg-input)">⚔️ <b>Adversarial Review</b> — devil's advocate at every stage</div>
        </div>
    </div>
    <div class="card"><h2>{ICON_CLOCK} Recent Activity</h2>{rows}</div>''', "dashboard")

# ─── NEW PIPELINE ───
@app.route("/new")
@login_required
def new_pipeline():
    has_elevenlabs = bool(os.getenv("ELEVENLABS_API_KEY"))
    el_note = "" if has_elevenlabs else ' <span class="feat-tag ip-risk">No API key</span>'
    return layout(f'''
    <h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:24px">{ICON_PLUS} New Slot Pipeline</h2>
    <form action="/api/pipeline" method="POST">
    <div class="card"><h2>🎰 Game Concept</h2>
    <label>Theme / Concept</label><input name="theme" placeholder="e.g. Ancient Egyptian curse with escalating darkness" required>
    <div class="row2"><div><label>Target Jurisdictions (any — comma-separated)</label><input name="target_markets" placeholder="e.g. Georgia, Texas, UK, Malta" value="Georgia, Texas">
    <p style="font-size:10px;color:var(--text-muted);margin-top:-12px;margin-bottom:12px">Enter any jurisdiction: US states, countries, or regulated markets. State Recon runs automatically for unknown US states.</p>
    </div>
    <div><label>Volatility</label><select name="volatility"><option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option><option value="very_high">Very High</option></select></div></div></div>

    <div class="card"><h2>📐 Math & Grid</h2>
    <div class="row3"><div><label>Target RTP %</label><input type="number" name="target_rtp" value="96.0" step="0.1" min="85" max="99"></div><div><label>Grid Cols</label><input type="number" name="grid_cols" value="5"></div><div><label>Grid Rows</label><input type="number" name="grid_rows" value="3"></div></div>
    <div class="row3"><div><label>Ways / Lines</label><input type="number" name="ways_or_lines" value="243"></div><div><label>Max Win Multiplier</label><input type="number" name="max_win_multiplier" value="5000"></div><div><label>Art Style</label><input name="art_style" value="Cinematic realism"></div></div></div>

    <div class="card"><h2>⚡ Features & Mechanics</h2>
    <div class="feature-grid">
        <label><input type="checkbox" name="features" value="free_spins" checked> Free Spins <span class="feat-tag safe">✓ Safe</span></label>
        <label><input type="checkbox" name="features" value="multipliers" checked> Multipliers <span class="feat-tag safe">✓ Safe</span></label>
        <label><input type="checkbox" name="features" value="expanding_wilds"> Expanding Wilds <span class="feat-tag safe">✓ Safe</span></label>
        <label><input type="checkbox" name="features" value="cascading_reels"> Cascading Reels <span class="feat-tag safe">Low IP</span></label>
        <label><input type="checkbox" name="features" value="mystery_symbols"> Mystery Symbols <span class="feat-tag safe">✓ Safe</span></label>
        <label><input type="checkbox" name="features" value="walking_wilds"> Walking Wilds <span class="feat-tag safe">Low IP</span></label>
        <label><input type="checkbox" name="features" value="cluster_pays"> Cluster Pays <span class="feat-tag safe">Low IP</span></label>
        <label><input type="checkbox" name="features" value="hold_and_spin"> Hold & Spin <span class="feat-tag ip-risk">Med IP</span></label>
        <label><input type="checkbox" name="features" value="bonus_buy"> Bonus Buy <span class="feat-tag banned">UK/SE ban</span></label>
        <label><input type="checkbox" name="features" value="progressive_jackpot"> Progressive Jackpot <span class="feat-tag ip-risk">+cost</span></label>
        <label><input type="checkbox" name="features" value="megaways"> Megaways™ <span class="feat-tag ip-risk">License req</span></label>
        <label><input type="checkbox" name="features" value="split_symbols"> Split Symbols <span class="feat-tag safe">Low IP</span></label>
    </div>
    <p style="font-size:10px;color:var(--text-muted);margin-top:12px">IP risk tags are pre-flight estimates. Patent Scanner runs full check during pipeline execution.</p>
    <div style="margin-top:16px"><label>Competitor References</label><input name="competitor_references" placeholder="e.g. Book of Dead, Legacy of Dead, Sweet Bonanza">
    <label>Special Requirements</label><textarea name="special_requirements" placeholder="e.g. Must support mobile portrait mode, needs 5+ free spin retriggers, dark moody atmosphere..."></textarea></div></div>

    <div class="card"><h2>🤖 Pipeline Intelligence</h2>
    <div class="toggle-section">
        <div class="toggle-item"><input type="checkbox" name="enable_recon" value="on" checked id="recon"><label for="recon">🌐 Auto State Recon</label><span class="toggle-desc">Research unknown US state laws before pipeline</span></div>
        <div class="toggle-item"><input type="checkbox" name="enable_prototype" value="on" checked id="proto"><label for="proto">🎮 HTML5 Prototype</label><span class="toggle-desc">Auto-generate playable demo</span></div>
        <div class="toggle-item"><input type="checkbox" name="enable_sound" value="on" {'checked' if has_elevenlabs else ''} id="snd"><label for="snd">🔊 AI Sound Design{el_note}</label><span class="toggle-desc">ElevenLabs SFX generation</span></div>
        <div class="toggle-item"><input type="checkbox" name="enable_cert_plan" value="on" checked id="cert"><label for="cert">📋 Certification Plan</label><span class="toggle-desc">Test lab + timeline + cost</span></div>
        <div class="toggle-item"><input type="checkbox" name="enable_patent_scan" value="on" checked id="pat"><label for="pat">🔒 Patent/IP Scan</label><span class="toggle-desc">Check mechanics for conflicts</span></div>
    </div></div>

    <div class="card"><h2>⚙️ Execution Mode</h2>
    <div style="display:flex;gap:24px;align-items:center">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin:0"><input type="radio" name="interactive" value="" checked style="width:auto;margin:0"> <span style="text-transform:none;font-size:13px;color:var(--text-bright);font-weight:600">Auto Mode</span><span style="font-size:11px;color:var(--text-muted);margin-left:4px">— runs fully autonomous</span></label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin:0"><input type="radio" name="interactive" value="on" style="width:auto;margin:0"> <span style="text-transform:none;font-size:13px;color:var(--accent);font-weight:600">Interactive Mode</span><span style="font-size:11px;color:var(--text-muted);margin-left:4px">— pauses for your review at each stage</span></label>
    </div></div>
    <button type="submit" class="btn btn-primary btn-full" style="padding:16px;font-size:15px">🚀 Launch Pipeline</button></form>''', "new")

# ─── STATE RECON ───
@app.route("/recon")
@login_required
def recon_page():
    return layout(f'''
    <h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:4px">{ICON_GLOBE} State Recon</h2>
    <p style="color:var(--text-muted);font-size:13px;margin-bottom:24px">Point at any US state. AI agents research laws, find loopholes, design compliant games, and write defense briefs.</p>
    <div class="card"><h2>{ICON_SEARCH} Research a State</h2><form action="/api/recon" method="POST"><label>US State Name</label><div class="recon-input-group"><input name="state" placeholder="e.g. North Carolina" required><button type="submit" class="btn btn-primary">Launch Recon</button></div></form></div>
    <div class="card"><h2>Pipeline Stages</h2><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;text-align:center;padding:12px 0">
    <div><div style="font-size:24px;margin-bottom:6px">&#128269;</div><div style="font-size:12px;font-weight:600;color:var(--text-bright)">Legal Research</div><div style="font-size:11px;color:var(--text-muted)">Statutes, case law, AG opinions</div></div>
    <div><div style="font-size:24px;margin-bottom:6px">&#9878;&#65039;</div><div style="font-size:12px;font-weight:600;color:var(--text-bright)">Definition Analysis</div><div style="font-size:11px;color:var(--text-muted)">Element mapping, loophole ID</div></div>
    <div><div style="font-size:24px;margin-bottom:6px">&#127918;</div><div style="font-size:12px;font-weight:600;color:var(--text-bright)">Game Architecture</div><div style="font-size:11px;color:var(--text-muted)">Compliant mechanics design</div></div>
    <div><div style="font-size:24px;margin-bottom:6px">&#128203;</div><div style="font-size:12px;font-weight:600;color:var(--text-bright)">Defense Brief</div><div style="font-size:11px;color:var(--text-muted)">Courtroom-ready mapping</div></div></div></div>''', "recon")

# ─── HISTORY ───
@app.route("/history")
@login_required
def history_page():
    user = current_user()
    db = get_db()
    jobs = db.execute("SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user["id"],)).fetchall()
    db.close()
    rows = ""
    for job in jobs:
        jid,status = job["id"], live_jobs.get(job["id"],{}).get("status",job["status"])
        bc = {"running":"badge-running","complete":"badge-complete","failed":"badge-failed"}.get(status,"badge-queued")
        tl = "Slot" if job["job_type"]=="slot_pipeline" else "Recon"
        dt = job["created_at"][:16].replace("T"," ") if job["created_at"] else ""
        act = f'<a href="/job/{jid}/files" class="btn btn-ghost btn-sm">Files</a>' if status=="complete" else (f'<a href="/job/{jid}/logs" class="btn btn-ghost btn-sm" style="border-color:var(--accent);color:var(--accent)">Watch Live</a>' if status=="running" else "")
        err = f'<div style="font-size:11px;color:var(--danger);margin-top:2px">{job["error"][:80]}...</div>' if job["error"] else ""
        rows += f'<div class="history-item"><div><div class="history-title">{job["title"]}</div><div class="history-type">{tl}{err}</div></div><div><span class="badge {bc}">{status}</span></div><div class="history-date">{dt}</div><div class="history-actions">{act}</div></div>'
    if not rows: rows = '<div class="empty-state"><h3>No history yet</h3></div>'
    return layout(f'<h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:24px">{ICON_CLOCK} Pipeline History</h2><div class="card" style="padding:0;overflow:hidden">{rows}</div>', "history")

# ─── FILES ───
@app.route("/files")
@login_required
def files_page():
    dirs = []
    if OUTPUT_DIR.exists():
        for d in sorted(OUTPUT_DIR.iterdir(), reverse=True):
            if d.is_dir():
                fc = sum(1 for _ in d.rglob("*") if _.is_file())
                ts = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                dirs.append({"name":d.name,"files":fc,"size":f"{ts/1024:.0f} KB" if ts<1048576 else f"{ts/1048576:.1f} MB","mtime":datetime.fromtimestamp(d.stat().st_mtime).strftime("%Y-%m-%d %H:%M")})
    rows = "".join(f'<div class="file-row"><a href="/files/{d["name"]}">{ICON_FOLDER} {d["name"]}</a><span class="file-size">{d["files"]} files &middot; {d["size"]}</span></div>' for d in dirs)
    if not rows: rows = '<div class="empty-state"><h3>No output files yet</h3></div>'
    return layout(f'<h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:24px">{ICON_FOLDER} Output Files</h2><div class="card" style="padding:0;overflow:hidden">{rows}</div>', "files")

@app.route("/files/<path:subpath>")
@login_required
def browse_files(subpath):
    target = OUTPUT_DIR / subpath
    if not target.exists(): return "Not found", 404
    if target.is_file(): return send_from_directory(target.parent, target.name)
    files = [{"path":str(f.relative_to(target)),"url":f"/files/{f.relative_to(OUTPUT_DIR)}","size":f"{f.stat().st_size/1024:.1f} KB"} for f in sorted(target.rglob("*")) if f.is_file()]
    rows = "".join(f'<div class="file-row"><a href="{f["url"]}">{f["path"]}</a><span class="file-size">{f["size"]}</span></div>' for f in files)
    return layout(f'<div style="margin-bottom:20px"><a href="/files" style="color:var(--accent);font-size:12px;text-decoration:none">&larr; Back</a></div><h2 style="font-size:18px;font-weight:700;color:var(--text-bright);margin-bottom:16px">{subpath}</h2><div class="card" style="padding:0;overflow:hidden">{rows}</div>', "files")

# ─── JOB FILES ───
@app.route("/job/<job_id>/files")
@login_required
def job_files(job_id):
    db = get_db(); job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone(); db.close()
    if not job or not job["output_dir"]: return "Not found", 404
    op = Path(job["output_dir"])
    if not op.exists(): return layout('<div class="card"><p style="color:var(--text-muted)">Output no longer exists.</p></div>')

    # Collect all files
    all_files = sorted(op.rglob("*"))
    files = [{"path":str(f.relative_to(op)),"url":f"/job/{job_id}/dl/{f.relative_to(op)}","size":f"{f.stat().st_size/1024:.1f} KB","ext":f.suffix.lower()} for f in all_files if f.is_file()]

    # Prototype section
    proto_html = ""
    proto_files = [f for f in files if f["path"].startswith("07_prototype") and f["ext"] == ".html"]
    if proto_files:
        proto_html = f'''<div class="card"><h2>🎮 Playable Prototype</h2>
            <iframe src="{proto_files[0]['url']}" class="proto-frame" title="Game Prototype"></iframe>
            <div style="margin-top:8px;text-align:center"><a href="{proto_files[0]['url']}" target="_blank" class="btn btn-ghost btn-sm">Open in new tab ↗</a></div></div>'''

    # Audio section
    audio_html = ""
    audio_files = [f for f in files if f["path"].startswith("04_audio") and f["ext"] in (".mp3", ".wav")]
    if audio_files:
        audio_rows = ""
        for af in audio_files:
            name = Path(af["path"]).stem
            audio_rows += f'<div class="audio-player"><span class="audio-name">{name}</span><audio controls preload="none" src="{af["url"]}"></audio><span class="file-size">{af["size"]}</span></div>'
        audio_html = f'<div class="card"><h2>🔊 AI Sound Design ({len(audio_files)} sounds)</h2><div style="max-height:400px;overflow-y:auto">{audio_rows}</div></div>'

    # Cert plan section
    cert_html = ""
    cert_file = op / "05_legal" / "certification_plan.json"
    if cert_file.exists():
        try:
            cert = json.loads(cert_file.read_text())
            markets = list(cert.get("per_market", {}).keys())
            timeline = cert.get("total_timeline", {})
            cost = cert.get("total_cost", {})
            lab = cert.get("recommended_lab", {})
            flags = cert.get("critical_flags", [])

            flags_html = "".join(f'<div style="padding:6px 10px;background:#ef444415;border-radius:6px;font-size:12px;color:var(--danger);margin-bottom:4px">⚠️ {fl}</div>' for fl in flags)

            cert_html = f'''<div class="card"><h2>📋 Certification Plan</h2>
                <div class="row3" style="margin-bottom:16px">
                    <div><label>Recommended Lab</label><div style="font-size:16px;font-weight:700;color:var(--accent)">{lab.get("name","TBD")}</div><div style="font-size:11px;color:var(--text-muted)">Covers {lab.get("covers_markets",0)}/{len(markets)} markets</div></div>
                    <div><label>Timeline (Parallel)</label><div style="font-size:16px;font-weight:700;color:var(--text-bright)">{timeline.get("parallel_testing_weeks","?")} weeks</div><div style="font-size:11px;color:var(--text-muted)">vs {timeline.get("sequential_testing_weeks","?")}w sequential</div></div>
                    <div><label>Total Cost Estimate</label><div style="font-size:16px;font-weight:700;color:var(--warning)">{cost.get("estimated_range","TBD")}</div></div>
                </div>
                {flags_html}
                <div style="margin-top:12px"><a href="/job/{job_id}/dl/05_legal/certification_plan.json" class="btn btn-ghost btn-sm">Download full plan JSON ↓</a></div></div>'''
        except Exception:
            pass

    # Patent scan section
    patent_html = ""
    patent_file = op / "00_preflight" / "patent_scan.json"
    if patent_file.exists():
        try:
            pscan = json.loads(patent_file.read_text())
            risk = pscan.get("risk_assessment", {})
            risk_level = risk.get("overall_ip_risk", "UNKNOWN")
            risk_color = {"HIGH":"var(--danger)","MEDIUM":"var(--warning)","LOW":"var(--success)"}.get(risk_level, "var(--text-muted)")
            hits = pscan.get("known_patent_hits", [])
            hits_rows = []
            for h in hits:
                risk_str = h.get("risk", "")
                rc = "var(--danger)" if risk_str.startswith("HIGH") else ("var(--warning)" if "MEDIUM" in risk_str else "var(--text-muted)")
                hits_rows.append(f'<div style="padding:6px 10px;background:var(--bg-input);border-radius:6px;font-size:12px;margin-bottom:4px"><b>{h.get("mechanic","")}</b> — {h.get("holder","")} <span style="color:{rc}">({risk_str})</span></div>')
            hits_html = "".join(hits_rows)

            patent_html = f'''<div class="card"><h2>🔒 Patent/IP Scan</h2>
                <div style="margin-bottom:12px"><span style="font-size:16px;font-weight:700;color:{risk_color}">{risk_level} RISK</span>
                <span style="font-size:12px;color:var(--text-muted);margin-left:8px">{risk.get("patent_conflicts",0)} conflicts, {risk.get("trademark_similar_names",0)} trademark matches</span></div>
                {hits_html if hits_html else '<div style="font-size:12px;color:var(--success)">No known patent conflicts detected.</div>'}
            </div>'''
        except Exception:
            pass

    # Regular file list
    rows = "".join(f'<div class="file-row"><a href="{f["url"]}">{f["path"]}</a><span class="file-size">{f["size"]}</span></div>' for f in files)

    return layout(f'''<div style="margin-bottom:20px"><a href="/history" style="color:var(--accent);font-size:12px;text-decoration:none">&larr; Back to History</a></div>
    <h2 style="font-size:18px;font-weight:700;color:var(--text-bright);margin-bottom:4px">{job["title"]}</h2>
    <p style="color:var(--text-muted);font-size:12px;margin-bottom:16px">{len(files)} files generated</p>
    {proto_html}{audio_html}{patent_html}{cert_html}
    <div class="card" style="padding:0;overflow:hidden"><div style="padding:16px 16px 8px"><h2>📁 All Files</h2></div>{rows}</div>''', "history")

@app.route("/job/<job_id>/dl/<path:fp>")
@login_required
def job_dl(job_id, fp):
    db = get_db(); job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone(); db.close()
    if not job or not job["output_dir"]: return "Not found", 404
    return send_from_directory(Path(job["output_dir"]), fp)

# ─── QDRANT ───
@app.route("/qdrant")
@login_required
def qdrant_status():
    try:
        from tools.qdrant_store import JurisdictionStore
        status = JurisdictionStore().get_status()
    except Exception as e:
        status = {"status":"ERROR","message":str(e),"jurisdictions":[],"total_vectors":0}
    bc = "badge-complete" if status["status"]=="ONLINE" else "badge-failed"
    jhtml = "".join(f'<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">{j}</div>' for j in status.get("jurisdictions",[])) or '<div style="color:var(--text-muted);font-size:13px;padding:12px 0">No jurisdictions yet. Run a State Recon.</div>'
    return layout(f'''
    <h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:24px">{ICON_DB} Qdrant Vector Database</h2>
    <div class="card"><h2>Connection <span class="badge {bc}" style="margin-left:8px">{status["status"]}</span></h2>
    <div class="row2" style="margin-top:12px"><div><label>Total Vectors</label><div style="font-size:20px;font-weight:700;color:var(--accent)">{status.get("total_vectors",0)}</div></div>
    <div><label>Jurisdictions</label><div style="font-size:20px;font-weight:700;color:var(--accent)">{len(status.get("jurisdictions",[]))}</div></div></div></div>
    <div class="card"><h2>Researched Jurisdictions</h2>{jhtml}</div>''', "qdrant")

# ─── REVIEWS (Web HITL) ───
@app.route("/reviews")
@login_required
def reviews_page():
    from tools.web_hitl import get_pending_reviews
    pending = get_pending_reviews()
    # Also get resolved reviews
    resolved = []
    try:
        db = get_db()
        resolved = db.execute(
            "SELECT r.*, j.title as job_title FROM reviews r JOIN jobs j ON r.job_id=j.id "
            "WHERE r.status!='pending' ORDER BY r.resolved_at DESC LIMIT 20"
        ).fetchall()
        db.close()
    except Exception:
        pass

    pending_html = ""
    for r in pending:
        pending_html += f'''<div class="history-item" style="grid-template-columns:1fr 140px 100px">
            <div><div class="history-title">{r["title"]}</div><div class="history-type">{r["job_title"]} &middot; {r["stage"]}</div></div>
            <div class="history-date">{r["created_at"][:16] if r["created_at"] else ""}</div>
            <div class="history-actions"><a href="/review/{r["id"]}" class="btn btn-primary btn-sm">Review</a></div>
        </div>'''
    if not pending_html:
        pending_html = '<div class="empty-state"><h3>No pending reviews</h3><p>Launch a pipeline in Interactive Mode to see checkpoints here.</p></div>'

    resolved_html = ""
    for r in resolved:
        r = dict(r)
        status = "Approved" if r.get("approved") else "Rejected"
        bc = "badge-complete" if r.get("approved") else "badge-failed"
        resolved_html += f'''<div class="history-item" style="grid-template-columns:1fr 100px 140px">
            <div><div class="history-title">{r["title"]}</div><div class="history-type">{r.get("job_title","")} &middot; {r.get("feedback","")[:50]}</div></div>
            <div><span class="badge {bc}">{status}</span></div>
            <div class="history-date">{r.get("resolved_at","")[:16]}</div>
        </div>'''

    return layout(f'''
    <h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:24px">{ICON_REVIEW} Pipeline Reviews</h2>
    <div class="card"><h2 style="color:var(--accent)">Pending Reviews <span class="badge badge-running" style="margin-left:8px">{len(pending)}</span></h2>{pending_html}</div>
    {"<div class='card'><h2>Resolved</h2>" + resolved_html + "</div>" if resolved_html else ""}''', "reviews")


@app.route("/review/<review_id>")
@login_required
def review_detail(review_id):
    from tools.web_hitl import get_review
    import json as _json
    review = get_review(review_id)
    if not review:
        return "Review not found", 404

    files = _json.loads(review.get("files","[]")) if review.get("files") else []
    output_dir = review.get("output_dir","")

    # Build file list with download links
    files_html = ""
    if files and output_dir:
        for f in files:
            fpath = Path(output_dir) / f
            if fpath.exists():
                ext = fpath.suffix.lower()
                # Show image previews inline
                if ext in (".png",".jpg",".jpeg",".webp"):
                    files_html += f'<div style="margin:8px 0"><div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;font-family:JetBrains Mono,monospace">{f}</div><img src="/review/{review_id}/file/{f}" style="max-width:100%;border-radius:8px;border:1px solid var(--border)"></div>'
                else:
                    files_html += f'<div class="file-row"><a href="/review/{review_id}/file/{f}">{f}</a><span class="file-size">{fpath.stat().st_size/1024:.1f} KB</span></div>'

    if not files_html:
        files_html = '<div style="color:var(--text-muted);font-size:13px;padding:12px 0">No files to preview.</div>'

    already_resolved = review["status"] != "pending"
    form_html = ""
    if already_resolved:
        result = "Approved" if review.get("approved") else "Rejected"
        form_html = f'<div class="card" style="border-color:var(--success) !important"><h2>Already {result}</h2><p style="color:var(--text-muted)">{review.get("feedback","")}</p></div>'
    else:
        form_html = f'''<div class="card">
        <h2>Your Decision</h2>
        <form action="/api/review/{review_id}" method="POST">
            <label>Feedback / Art Changes / Notes</label>
            <textarea name="feedback" placeholder="e.g. Make the symbols darker, increase contrast on the wild symbol, add more gold accents..." rows="4"></textarea>
            <div style="display:flex;gap:12px;margin-top:8px">
                <button type="submit" name="action" value="approve" class="btn btn-primary" style="flex:1;padding:14px">Approve &amp; Continue</button>
                <button type="submit" name="action" value="reject" class="btn btn-ghost" style="flex:1;padding:14px;border-color:var(--danger);color:var(--danger)">Reject &amp; Revise</button>
            </div>
        </form></div>'''

    return layout(f'''
    <div style="margin-bottom:20px"><a href="/reviews" style="color:var(--accent);font-size:12px;text-decoration:none">&larr; Back to Reviews</a></div>
    <h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:4px">{review["title"]}</h2>
    <p style="color:var(--text-muted);font-size:12px;margin-bottom:24px">{review.get("job_title","")} &middot; Stage: {review["stage"]}</p>

    <div class="card"><h2>Summary</h2><div style="font-size:13px;line-height:1.7;white-space:pre-wrap">{review["summary"]}</div></div>
    <div class="card" style="padding:0;overflow:hidden"><div style="padding:16px 16px 8px"><h2 style="margin-bottom:8px">Generated Files</h2></div>{files_html}</div>
    {form_html}''', "reviews")


@app.route("/review/<review_id>/file/<path:fp>")
@login_required
def review_file(review_id, fp):
    from tools.web_hitl import get_review
    review = get_review(review_id)
    if not review or not review.get("output_dir"):
        return "Not found", 404
    return send_from_directory(Path(review["output_dir"]), fp)


@app.route("/api/review/<review_id>", methods=["POST"])
@login_required
def api_submit_review(review_id):
    from tools.web_hitl import submit_review
    action = request.form.get("action","approve")
    feedback = request.form.get("feedback","")
    approved = (action == "approve")
    submit_review(review_id, approved=approved, feedback=feedback)
    return redirect("/reviews")


# ─── SETTINGS ───
@app.route("/settings")
@login_required
def settings_page():
    keys = {
        "OPENAI_API_KEY": {"label": "OpenAI API Key", "icon": "🧠", "desc": "GPT-4o for all agents, DALL-E 3 for images, Vision QA", "required": True},
        "SERPER_API_KEY": {"label": "Serper API Key", "icon": "🔍", "desc": "Web search, patent search, trend radar, competitor teardown", "required": True},
        "ELEVENLABS_API_KEY": {"label": "ElevenLabs API Key", "icon": "🔊", "desc": "AI sound effect generation (13 core game sounds)", "required": False},
        "QDRANT_URL": {"label": "Qdrant URL", "icon": "🗃️", "desc": "Vector DB for regulation storage + knowledge base", "required": False},
        "QDRANT_API_KEY": {"label": "Qdrant API Key", "icon": "🔑", "desc": "Auth for Qdrant Cloud", "required": False},
        "GOOGLE_CLIENT_ID": {"label": "Google OAuth Client ID", "icon": "🔐", "desc": "Google sign-in", "required": True},
        "GOOGLE_CLIENT_SECRET": {"label": "Google OAuth Secret", "icon": "🔐", "desc": "Google sign-in", "required": True},
    }

    rows = ""
    for env_key, info in keys.items():
        val = os.getenv(env_key, "")
        is_set = bool(val) and val not in ("your-openai-key", "your-serper-key", "your-elevenlabs-key", "your-qdrant-key", "your-qdrant-url", "your-google-client-id", "your-google-client-secret")
        masked = val[:8] + "..." + val[-4:] if is_set and len(val) > 12 else ("Set" if is_set else "Not configured")
        bc = "badge-complete" if is_set else ("badge-failed" if info["required"] else "badge-queued")
        status = "Connected" if is_set else ("Required" if info["required"] else "Optional")
        rows += f'''<div class="file-row" style="padding:14px 16px;gap:16px">
            <div style="display:flex;align-items:center;gap:12px;flex:1">
                <span style="font-size:20px">{info["icon"]}</span>
                <div><div style="font-weight:600;color:var(--text-bright);font-size:13px">{info["label"]}</div>
                <div style="font-size:11px;color:var(--text-muted)">{info["desc"]}</div></div>
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted);min-width:120px">{masked}</div>
            <span class="badge {bc}">{status}</span>
        </div>'''

    return layout(f'''
    <h2 style="font-size:20px;font-weight:800;color:var(--text-bright);margin-bottom:4px">{ICON_SETTINGS} Settings</h2>
    <p style="color:var(--text-muted);font-size:13px;margin-bottom:24px">API keys and integrations. Configure in <code style="font-family:'JetBrains Mono',monospace;background:var(--bg-input);padding:2px 6px;border-radius:4px">.env</code> file.</p>
    <div class="card" style="padding:0;overflow:hidden"><div style="padding:16px 16px 8px"><h2>🔗 API Integrations</h2></div>{rows}</div>
    <div class="card"><h2>📋 Quick Setup</h2>
    <pre style="background:var(--bg-input);padding:16px;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text);overflow-x:auto;line-height:1.8">
# Copy .env.example to .env and fill in your keys:
cp .env.example .env

# Required:
OPENAI_API_KEY=sk-...          # OpenAI (GPT-4o + DALL-E 3)
SERPER_API_KEY=...              # serper.dev (free tier: 2500 searches)

# Optional (Tier 2):
ELEVENLABS_API_KEY=...          # elevenlabs.io ($5/mo starter for SFX)

# Optional (State Recon):
QDRANT_URL=...                  # Qdrant Cloud or self-hosted
QDRANT_API_KEY=...
</pre></div>

    <div class="card"><h2>🏗️ Pipeline Version</h2>
    <div class="row2">
        <div><label>Version</label><div style="font-size:16px;font-weight:700;color:var(--accent)">v4.0.0</div></div>
        <div><label>Active Upgrades</label><div style="font-size:16px;font-weight:700;color:var(--text-bright)">15</div></div>
    </div>
    <div style="margin-top:12px;font-size:12px;color:var(--text-muted)">
        Tier 1: Vision QA, Paytable Optimizer, Jurisdiction Engine, Player Behavior, Agent Debate, Trend Radar<br>
        Tier 2: Patent Scanner, HTML5 Prototype, Sound Design, Certification Planner<br>
        Core: Deep Research, Competitor Teardown, Knowledge Base, Adversarial Review, Web HITL
    </div></div>''', "settings")


# ─── API ───
@app.route("/api/pipeline", methods=["POST"])
@login_required
def api_launch_pipeline():
    user = current_user(); job_id = str(uuid.uuid4())[:8]
    params = {"theme":request.form["theme"],"target_markets":[m.strip() for m in request.form.get("target_markets","Georgia, Texas").split(",")],"volatility":request.form.get("volatility","medium"),"target_rtp":float(request.form.get("target_rtp",96)),"grid_cols":int(request.form.get("grid_cols",5)),"grid_rows":int(request.form.get("grid_rows",3)),"ways_or_lines":request.form.get("ways_or_lines","243"),"max_win_multiplier":int(request.form.get("max_win_multiplier",5000)),"art_style":request.form.get("art_style","Cinematic realism"),"requested_features":request.form.getlist("features"),"competitor_references":[r.strip() for r in request.form.get("competitor_references","").split(",") if r.strip()],"special_requirements":request.form.get("special_requirements",""),"enable_recon":request.form.get("enable_recon")=="on"}
    db = get_db(); db.execute("INSERT INTO jobs (id,user_id,job_type,title,params,status) VALUES (?,?,?,?,?,?)", (job_id,user["id"],"slot_pipeline",params["theme"],json.dumps(params),"queued")); db.commit(); db.close()
    live_jobs[job_id] = {"status":"queued","current_stage":"Starting","params":params,"interactive": request.form.get("interactive") == "on"}
    run_slot_pipeline(job_id)
    return redirect(f"/job/{job_id}/logs")

@app.route("/api/recon", methods=["POST"])
@login_required
def api_launch_recon():
    user = current_user(); sn = request.form["state"].strip(); job_id = str(uuid.uuid4())[:8]
    db = get_db(); db.execute("INSERT INTO jobs (id,user_id,job_type,title,params,status) VALUES (?,?,?,?,?,?)", (job_id,user["id"],"state_recon",f"Recon: {sn}",json.dumps({"state":sn}),"queued")); db.commit(); db.close()
    live_jobs[job_id] = {"status":"queued","current_stage":"Starting"}
    run_state_recon(job_id, sn)
    return redirect(f"/job/{job_id}/logs")

@app.route("/api/status/<job_id>")
@login_required
def api_job_status(job_id):
    # DB is the source of truth (shared across gunicorn workers + subprocesses)
    db = get_db()
    job = db.execute("SELECT status,current_stage,error FROM jobs WHERE id=?", (job_id,)).fetchone()
    db.close()
    if not job:
        return jsonify({"error": "Not found"}), 404
    result = dict(job)
    # Supplement with PID from live_jobs if available (same process only)
    live = live_jobs.get(job_id, {})
    if live.get("pid"):
        result["pid"] = live["pid"]
    return jsonify(result)


@app.route("/api/logs/<job_id>")
@login_required
def api_log_stream(job_id):
    """SSE endpoint — streams live log lines from the worker subprocess."""
    log_path = LOG_DIR / f"{job_id}.log"

    def generate():
        # Wait for log file to appear (worker may still be starting)
        waited = 0
        while not log_path.exists() and waited < 15:
            time.sleep(0.5)
            waited += 0.5
            yield f"data: Waiting for worker to start...\n\n"
        if not log_path.exists():
            yield f"data: [ERROR] Log file not found for job {job_id}\n\n"
            return

        with open(log_path, "r") as f:
            # Send existing content first
            for line in f:
                yield f"data: {line.rstrip()}\n\n"
            # Then tail for new lines
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    # Check if job is done
                    db = get_db()
                    job = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
                    db.close()
                    if job and job["status"] in ("complete", "failed"):
                        # Read any remaining lines
                        for remaining in f:
                            yield f"data: {remaining.rstrip()}\n\n"
                        yield f"data: [JOB {job['status'].upper()}]\n\n"
                        return
                    time.sleep(1)

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
    })


@app.route("/job/<job_id>/logs")
@login_required
def job_logs_page(job_id):
    db = get_db(); job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone(); db.close()
    if not job: return "Not found", 404
    status = live_jobs.get(job_id, {}).get("status", job["status"])
    return layout(f'''
    <div style="margin-bottom:20px"><a href="/history" style="color:var(--accent);font-size:12px;text-decoration:none;cursor:pointer">&larr; Back to History</a></div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <div>
            <h2 style="font-size:18px;font-weight:700;color:var(--text-bright);margin-bottom:4px">{job["title"]} — Live Logs</h2>
            <div style="font-size:12px;color:var(--text-muted)">{job["job_type"]} &middot; <span id="jobStatus" class="badge badge-{'running' if status=='running' else 'complete' if status=='complete' else 'failed'}">{status}</span></div>
        </div>
        <div style="display:flex;gap:8px">
            <button onclick="clearLog()" class="btn btn-ghost btn-sm">Clear</button>
            <button onclick="scrollToBottom()" class="btn btn-ghost btn-sm">↓ Bottom</button>
            {f'<a href="/job/{job_id}/files" class="btn btn-primary btn-sm">View Files</a>' if status=='complete' else ''}
        </div>
    </div>
    <div id="logContainer" style="background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;font-family:'JetBrains Mono',monospace;font-size:11px;line-height:1.7;height:calc(100vh - 220px);overflow-y:auto;white-space:pre-wrap;color:var(--text)"></div>
    <script>
    const logEl = document.getElementById('logContainer');
    let autoScroll = true;
    logEl.addEventListener('scroll', () => {{
        autoScroll = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 50;
    }});
    function scrollToBottom() {{ logEl.scrollTop = logEl.scrollHeight; autoScroll = true; }}
    function clearLog() {{ logEl.innerHTML = ''; }}
    function colorize(text) {{
        if (text.includes('FAILED') || text.includes('ERROR') || text.includes('BLOCKER'))
            return '<span style="color:var(--danger)">' + text + '</span>';
        if (text.includes('COMPLETE') || text.includes('✅') || text.includes('complete'))
            return '<span style="color:var(--success)">' + text + '</span>';
        if (text.includes('WARN') || text.includes('⚠️'))
            return '<span style="color:var(--warning)">' + text + '</span>';
        if (text.includes('Stage') || text.includes('🛰️') || text.includes('📊') || text.includes('🎨') || text.includes('📦'))
            return '<span style="color:var(--accent)">' + text + '</span>';
        return text;
    }}

    const evtSource = new EventSource('/api/logs/{job_id}');
    evtSource.onmessage = (e) => {{
        const line = e.data;
        logEl.innerHTML += colorize(line) + '\\n';
        if (autoScroll) scrollToBottom();
        if (line.includes('[JOB COMPLETE]')) {{
            document.getElementById('jobStatus').className = 'badge badge-complete';
            document.getElementById('jobStatus').textContent = 'complete';
            evtSource.close();
        }}
        if (line.includes('[JOB FAILED]')) {{
            document.getElementById('jobStatus').className = 'badge badge-failed';
            document.getElementById('jobStatus').textContent = 'failed';
            evtSource.close();
        }}
    }};
    evtSource.onerror = () => {{ evtSource.close(); }};
    </script>''', "history")


# ─── BACKGROUND WORKERS (subprocess-based) ───

# Track running subprocesses for status polling
_running_procs = {}  # job_id → Popen

def _cleanup_finished():
    """Remove completed jobs from in-memory tracking dicts."""
    for jid in list(_running_procs):
        proc = _running_procs[jid]
        if proc.poll() is not None:  # Process finished
            _running_procs.pop(jid, None)
            live_jobs.pop(jid, None)

def _spawn_worker(job_id, job_type, *args):
    """Spawn a worker subprocess. No import locks, no deadlocks."""
    _cleanup_finished()  # Housekeeping on each spawn
    worker_path = Path(__file__).parent / "worker.py"
    cmd = ["python3", "-u", str(worker_path), job_type, job_id] + list(args)
    env = {
        **os.environ,
        "DB_PATH": DB_PATH,
        "LOG_DIR": str(LOG_DIR),
        # ── Kill CrewAI tracing prompt ──
        "CREWAI_TELEMETRY_OPT_OUT": "true",
        "OTEL_SDK_DISABLED": "true",
        "CREWAI_TRACING_ENABLED": "false",
        "DO_NOT_TRACK": "1",
        # ── OpenAI SDK retry config ──
        "OPENAI_MAX_RETRIES": "5",
        "OPENAI_TIMEOUT": "120",
    }
    proc = subprocess.Popen(
        cmd, env=env,
        stdin=subprocess.DEVNULL,   # Prevents tracing prompt from blocking
        stdout=subprocess.DEVNULL,  # Logs go to files, not pipe (avoids pipe buffer deadlock)
        stderr=subprocess.DEVNULL,
        cwd=str(Path(__file__).parent),
    )
    _running_procs[job_id] = proc
    live_jobs[job_id]["status"] = "running"
    live_jobs[job_id]["pid"] = proc.pid

def run_slot_pipeline(job_id):
    p = live_jobs[job_id]["params"]
    interactive = live_jobs[job_id].get("interactive", False)
    p["interactive"] = interactive
    _spawn_worker(job_id, "pipeline", json.dumps(p))

def run_state_recon(job_id, state_name):
    _spawn_worker(job_id, "recon", state_name)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"ARKAINBRAIN — http://localhost:{port}")
    app.run(debug=os.getenv("FLASK_DEBUG","false").lower()=="true", host="0.0.0.0", port=port)
