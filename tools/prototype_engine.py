"""
ARKAINBRAIN — AI-Powered HTML5 Prototype Generator

Option C Implementation:
- Solid engine template (always works, never breaks)
- DALL-E symbol images embedded as base64
- LLM-generated theme CSS (colors, gradients, particles)
- LLM-generated custom bonus round JavaScript
- Math model paytable data integration
- Audio file hookups
"""

import base64
import json
import os
import re
from pathlib import Path
from pydantic import BaseModel, Field


class PrototypeInput(BaseModel):
    game_title: str = Field(description="Game title")
    theme: str = Field(description="Game theme, e.g. 'Ancient Egyptian'")
    grid_cols: int = Field(default=5, description="Number of columns")
    grid_rows: int = Field(default=3, description="Number of rows")
    symbols: list[str] = Field(default_factory=list, description="Symbol names")
    paytable_summary: str = Field(default="", description="Paytable summary text")
    features: list[str] = Field(default_factory=list, description="Feature names")
    color_primary: str = Field(default="#1a1a2e", description="Primary background color")
    color_accent: str = Field(default="#e6b800", description="Accent color (gold, etc)")
    color_text: str = Field(default="#ffffff", description="Text color")
    target_rtp: float = Field(default=96.0, description="Target RTP")
    output_dir: str = Field(default="./output", description="Output directory")
    # New fields for AI customization
    art_dir: str = Field(default="", description="Path to art directory with DALL-E images")
    audio_dir: str = Field(default="", description="Path to audio directory with sound files")
    gdd_context: str = Field(default="", description="GDD summary for bonus round design")
    math_context: str = Field(default="", description="Math model summary for paytable")
    volatility: str = Field(default="medium", description="Volatility tier")
    max_win_multiplier: int = Field(default=5000, description="Max win multiplier")


# ── Symbol image discovery & base64 encoding ──

def _discover_symbols(art_dir: str, symbol_names: list[str]) -> dict:
    """
    Scan art directory for DALL-E-generated symbol PNGs.
    Returns {symbol_name: base64_data_uri} for found images.
    """
    if not art_dir or not Path(art_dir).exists():
        return {}

    art_path = Path(art_dir)
    found = {}

    # Look for PNGs matching symbol names
    for png in art_path.rglob("*.png"):
        name_lower = png.stem.lower().replace(" ", "_").replace("-", "_")
        for sym in symbol_names:
            sym_lower = sym.lower().replace(" ", "_").replace("-", "_")
            if sym_lower in name_lower or name_lower in sym_lower:
                if sym not in found:  # First match wins
                    try:
                        b64 = base64.b64encode(png.read_bytes()).decode("utf-8")
                        found[sym] = f"data:image/png;base64,{b64}"
                    except Exception:
                        pass

    # Also check for generic symbol files like symbol_1.png, high_pay_1.png
    for png in sorted(art_path.rglob("*.png")):
        name = png.stem.lower()
        if any(kw in name for kw in ("symbol", "sym", "high_pay", "low_pay", "wild", "scatter", "bonus")):
            # Map to unmatched symbols
            unmatched = [s for s in symbol_names if s not in found]
            if unmatched:
                try:
                    b64 = base64.b64encode(png.read_bytes()).decode("utf-8")
                    found[unmatched[0]] = f"data:image/png;base64,{b64}"
                except Exception:
                    pass

    return found


def _discover_background(art_dir: str) -> str:
    """Find background image and return as base64 data URI."""
    if not art_dir or not Path(art_dir).exists():
        return ""
    art_path = Path(art_dir)
    for png in art_path.rglob("*.png"):
        name = png.stem.lower()
        if any(kw in name for kw in ("background", "bg", "base_game", "backdrop")):
            try:
                b64 = base64.b64encode(png.read_bytes()).decode("utf-8")
                return f"data:image/png;base64,{b64}"
            except Exception:
                pass
    return ""


def _discover_audio(audio_dir: str) -> dict:
    """Find audio files and return {sound_type: base64_data_uri}."""
    if not audio_dir or not Path(audio_dir).exists():
        return {}
    found = {}
    audio_path = Path(audio_dir)
    for af in audio_path.rglob("*"):
        if af.suffix.lower() in (".mp3", ".wav"):
            name = af.stem.lower()
            mime = "audio/mpeg" if af.suffix == ".mp3" else "audio/wav"
            try:
                # Only embed small files (<500KB) to keep prototype reasonable
                if af.stat().st_size < 512_000:
                    b64 = base64.b64encode(af.read_bytes()).decode("utf-8")
                    found[name] = f"data:{mime};base64,{b64}"
            except Exception:
                pass
    return found


# ── LLM Theme + Bonus Generation ──

def _generate_theme_and_bonus(
    theme: str, features: list[str], symbols: list[str],
    gdd_context: str, volatility: str, grid_cols: int, grid_rows: int,
    color_primary: str, color_accent: str,
) -> dict:
    """
    Call GPT-4o-mini to generate:
    1. Theme-specific CSS (colors, gradients, particles, glow effects)
    2. Custom bonus round JavaScript

    Returns dict with keys: theme_css, bonus_js, bonus_name, bonus_trigger_count
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _fallback_theme(theme, color_primary, color_accent)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""You are a game UI designer and JavaScript developer.

GAME: "{theme}"
GRID: {grid_cols}x{grid_rows}
VOLATILITY: {volatility}
FEATURES: {', '.join(features)}
SYMBOLS: {', '.join(symbols[:8])}
CURRENT COLORS: primary={color_primary}, accent={color_accent}

GDD CONTEXT (if available):
{gdd_context[:2000] if gdd_context else 'Not available'}

Generate TWO things as JSON:

1. "theme_css" — CSS custom properties and theme-specific styles. Include:
   - --bg-gradient: a dramatic background gradient matching the theme
   - --reel-bg: reel cell background color
   - --reel-border: reel frame glow color
   - --win-glow: win celebration glow color
   - --particle-color: floating particle/ember color
   - Any theme-specific CSS classes for ambiance (max 15 lines of CSS)
   Keep it as CSS text, not JSON.

2. "bonus_js" — A complete JavaScript bonus round function. Pick the BEST bonus type for this theme:
   - Free Spins (if "free_spins" in features): Award N free spins with progressive multiplier
   - Pick & Click (for treasure/mystery themes): Grid of hidden prizes, player picks to reveal
   - Wheel of Fortune (for luck/fortune themes): Spinning wheel with prize segments
   - Hold & Respin (if "hold_and_spin" in features): Lock winning cells, 3 respins
   - Cascading Wins (if "cascading_reels" in features): Remove winning symbols, new ones fall down
   - Trail/Ladder Bonus (for adventure themes): Progress through levels collecting prizes

   The function signature MUST be: async function runBonusRound(bet, state)
   - bet: current bet amount
   - state: object with {{balance, totalWon, grid, COLS, ROWS, updateHUD, weightedRandom, showWin}}
   - Return: total bonus winnings (number)
   - Use DOM to show a bonus overlay (#bonusOverlay) with themed content
   - Include animations (use CSS transitions, not heavy JS animation)
   - Keep it under 80 lines of JS

3. "bonus_name" — Display name like "Tomb of Riches Free Spins" or "Dragon's Treasure Pick"
4. "bonus_trigger_count" — How many scatter/bonus symbols trigger it (3, 4, or 5)
5. "scatter_symbol_index" — Which symbol index (0-based) acts as scatter (suggest 3 or 4 for a high-pay symbol)

Return ONLY valid JSON, no markdown backticks, no explanation:
{{"theme_css": "...", "bonus_js": "...", "bonus_name": "...", "bonus_trigger_count": 3, "scatter_symbol_index": 3}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.7,
        )

        text = response.choices[0].message.content.strip()
        # Clean up potential markdown fences
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        result = json.loads(text)
        # Validate required keys
        if "theme_css" not in result or "bonus_js" not in result:
            return _fallback_theme(theme, color_primary, color_accent)
        return result

    except Exception as e:
        print(f"[PROTO] LLM theme generation failed: {e}, using fallback")
        return _fallback_theme(theme, color_primary, color_accent)


def _fallback_theme(theme: str, color_primary: str, color_accent: str) -> dict:
    """Fallback theme when LLM is unavailable."""
    return {
        "theme_css": f"""
:root {{
    --bg-gradient: linear-gradient(180deg, {color_primary} 0%, #000 100%);
    --reel-bg: {color_primary};
    --reel-border: {color_accent}44;
    --win-glow: {color_accent};
    --particle-color: {color_accent};
}}""",
        "bonus_js": """
async function runBonusRound(bet, state) {
    const overlay = document.getElementById('bonusOverlay');
    overlay.innerHTML = '<div class="bonus-content"><h2>🎰 FREE SPINS!</h2><p>5 Free Spins Awarded!</p></div>';
    overlay.classList.add('show');
    let totalWin = 0;
    for (let i = 0; i < 5; i++) {
        await new Promise(r => setTimeout(r, 1500));
        const spinWin = bet * (Math.random() * 5 + 1);
        totalWin += spinWin;
        overlay.querySelector('p').textContent = `Spin ${i+1}/5 — Won: ${spinWin.toFixed(2)} | Total: ${totalWin.toFixed(2)}`;
    }
    await new Promise(r => setTimeout(r, 1000));
    overlay.classList.remove('show');
    return totalWin;
}""",
        "bonus_name": "Free Spins Bonus",
        "bonus_trigger_count": 3,
        "scatter_symbol_index": 3,
    }


# ── Emoji fallbacks for when no DALL-E images exist ──

THEME_EMOJI_MAP = {
    "egypt": ["🏛️", "☀️", "🐍", "👁️", "💎", "A", "K", "Q", "J", "10"],
    "dragon": ["🐉", "🔥", "⚔️", "🛡️", "💎", "A", "K", "Q", "J", "10"],
    "ocean": ["🐙", "🦈", "🐚", "🌊", "💎", "A", "K", "Q", "J", "10"],
    "space": ["🚀", "🌟", "🪐", "👽", "💎", "A", "K", "Q", "J", "10"],
    "norse": ["⚡", "🔨", "🐺", "🛡️", "💎", "A", "K", "Q", "J", "10"],
    "asian": ["🐲", "🏮", "🎋", "🀄", "💎", "A", "K", "Q", "J", "10"],
    "fruit": ["🍒", "🍋", "🍊", "🍇", "⭐", "A", "K", "Q", "J", "10"],
    "horror": ["💀", "🦇", "🕷️", "🌙", "💎", "A", "K", "Q", "J", "10"],
    "gem": ["💎", "💠", "🔮", "✨", "⭐", "A", "K", "Q", "J", "10"],
    "default": ["👑", "💎", "🏆", "🌟", "🔮", "A", "K", "Q", "J", "10"],
}


def _get_themed_emoji(theme: str) -> list[str]:
    """Pick emoji set that matches the theme."""
    theme_lower = theme.lower()
    for key, emojis in THEME_EMOJI_MAP.items():
        if key in theme_lower:
            return emojis
    return THEME_EMOJI_MAP["default"]


# ── Main Assembly ──

def generate_prototype(
    game_title: str, theme: str,
    grid_cols: int = 5, grid_rows: int = 3,
    symbols: list[str] = None, features: list[str] = None,
    color_primary: str = "#1a1a2e", color_accent: str = "#e6b800",
    color_text: str = "#ffffff", target_rtp: float = 96.0,
    output_dir: str = "./output", paytable_summary: str = "",
    art_dir: str = "", audio_dir: str = "",
    gdd_context: str = "", math_context: str = "",
    volatility: str = "medium", max_win_multiplier: int = 5000,
) -> str:
    """
    Generate a complete, playable, AI-themed HTML5 slot prototype.
    Returns JSON with file_path and metadata.
    """

    symbols = symbols or _get_themed_emoji(theme)
    features = features or ["Free Spins"]

    # 1. Discover DALL-E images
    symbol_images = _discover_symbols(art_dir, symbols)
    bg_image = _discover_background(art_dir)
    audio_files = _discover_audio(audio_dir)
    has_images = len(symbol_images) > 0

    print(f"[PROTO] Found {len(symbol_images)} symbol images, bg={'yes' if bg_image else 'no'}, audio={len(audio_files)} files")

    # 2. Generate AI theme + bonus
    print(f"[PROTO] Generating AI theme & bonus round...")
    ai_gen = _generate_theme_and_bonus(
        theme, features, symbols, gdd_context,
        volatility, grid_cols, grid_rows,
        color_primary, color_accent,
    )
    theme_css = ai_gen.get("theme_css", "")
    bonus_js = ai_gen.get("bonus_js", "")
    bonus_name = ai_gen.get("bonus_name", "Bonus Round")
    bonus_trigger = ai_gen.get("bonus_trigger_count", 3)
    scatter_idx = ai_gen.get("scatter_symbol_index", 3)

    # 3. Build symbol data for JS
    high_pay = symbols[:4] if len(symbols) >= 4 else symbols
    low_pay = symbols[4:9] if len(symbols) > 4 else ["A", "K", "Q", "J"]
    all_syms = (high_pay + low_pay)[:9]  # Max 9 symbols

    # Build JS symbol array with weights and optional image data
    sym_entries = []
    for i, s in enumerate(all_syms):
        is_high = i < len(high_pay)
        weight = 2 if is_high else 5
        img_uri = symbol_images.get(s, "")
        # Escape for JS
        s_escaped = s.replace("'", "\\'").replace('"', '\\"')
        if img_uri:
            sym_entries.append(
                f'{{sym:"{s_escaped}",weight:{weight},img:"{img_uri}",isScatter:{str(i == scatter_idx).lower()}}}'
            )
        else:
            sym_entries.append(
                f'{{sym:"{s_escaped}",weight:{weight},img:"",isScatter:{str(i == scatter_idx).lower()}}}'
            )
    symbols_js = ",\n        ".join(sym_entries)

    # Build paytable
    pay_rows = ""
    for i, s in enumerate(high_pay):
        mult = max(2, 10 - i * 2)
        label = f'<img src="{symbol_images[s]}" style="width:32px;height:32px;object-fit:contain">' if s in symbol_images else s
        pay_rows += f'<tr><td class="sym-cell">{label}</td><td>{mult*5}×</td><td>{mult*3}×</td><td>{mult}×</td></tr>\n'
    for i, s in enumerate(low_pay):
        mult = max(1, 3 - i)
        label = f'<img src="{symbol_images[s]}" style="width:32px;height:32px;object-fit:contain">' if s in symbol_images else s
        pay_rows += f'<tr><td class="sym-cell">{label}</td><td>{mult*3}×</td><td>{mult*2}×</td><td>{mult}×</td></tr>\n'

    features_html = "".join(f"<li>{f}</li>" for f in features)

    # Audio JS (embed audio elements if available)
    audio_elements = ""
    audio_map = {}
    for snd_name, snd_uri in audio_files.items():
        audio_id = f"snd_{snd_name}"
        audio_elements += f'<audio id="{audio_id}" preload="auto" src="{snd_uri}"></audio>\n'
        # Map common sound types
        for key in ("spin", "win", "scatter", "bonus", "click", "ambient", "big", "mega"):
            if key in snd_name.lower():
                audio_map[key] = audio_id

    audio_play_js = "function playSound(type) {\n"
    if audio_map:
        audio_play_js += "    const map = " + json.dumps(audio_map) + ";\n"
        audio_play_js += "    const id = map[type]; if(id){try{const a=document.getElementById(id);if(a){a.currentTime=0;a.play().catch(()=>{})}}catch(e){}}\n"
    else:
        audio_play_js += "    // No audio files embedded\n"
    audio_play_js += "}"

    # Background style
    bg_style = f'background-image:url("{bg_image}");background-size:cover;background-position:center;' if bg_image else ""

    # 4. Assemble the HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>{game_title} — Prototype</title>
<style>
/* ── STRUCTURAL CSS (never changes) ── */
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,sans-serif;color:{color_text};min-height:100vh;display:flex;flex-direction:column;align-items:center;overflow-x:hidden;{bg_style}background-color:{color_primary}}}
.header{{padding:16px;text-align:center;position:relative;z-index:1}}
.header h1{{font-size:clamp(18px,5vw,28px);color:{color_accent};text-shadow:0 0 20px {color_accent}44,0 2px 4px rgba(0,0,0,0.5);letter-spacing:1px}}
.header .tag{{font-size:11px;opacity:0.5;margin-top:4px}}
.reel-window{{display:grid;grid-template-columns:repeat({grid_cols},1fr);gap:4px;padding:8px;background:#00000088;border-radius:12px;border:2px solid var(--reel-border,{color_accent}44);box-shadow:0 0 40px {color_accent}15,inset 0 0 30px rgba(0,0,0,0.3);margin:8px;max-width:520px;width:92vw;position:relative;z-index:1;backdrop-filter:blur(8px)}}
.cell{{width:100%;aspect-ratio:1;display:grid;place-items:center;background:var(--reel-bg,{color_primary});border-radius:6px;font-size:clamp(20px,6vw,36px);transition:all 0.15s;position:relative;overflow:hidden;border:1px solid rgba(255,255,255,0.05)}}
.cell img{{width:80%;height:80%;object-fit:contain;pointer-events:none}}
.cell.spinning{{animation:blur-spin 0.08s linear infinite}}
@keyframes blur-spin{{0%{{opacity:1;transform:translateY(0)}}50%{{opacity:0.2;transform:translateY(-10px)}}100%{{opacity:1;transform:translateY(0)}}}}
.cell.win{{background:var(--win-glow,{color_accent})22;box-shadow:inset 0 0 20px var(--win-glow,{color_accent})66;animation:glow-pulse 0.5s ease 3}}
@keyframes glow-pulse{{0%,100%{{box-shadow:inset 0 0 20px var(--win-glow,{color_accent})44}}50%{{box-shadow:inset 0 0 40px var(--win-glow,{color_accent})aa}}}}
.cell.scatter-highlight{{border:2px solid {color_accent};box-shadow:0 0 15px {color_accent}88}}
.hud{{display:flex;justify-content:space-between;align-items:center;padding:12px 20px;max-width:520px;width:92vw;font-size:13px;position:relative;z-index:1}}
.hud-item{{text-align:center}}
.hud-item .label{{font-size:10px;opacity:0.5;text-transform:uppercase}}
.hud-item .value{{font-size:18px;font-weight:700;color:{color_accent}}}
.win-display{{height:44px;display:grid;place-items:center;font-size:22px;font-weight:800;color:{color_accent};text-shadow:0 0 15px {color_accent};opacity:0;transition:opacity 0.3s;position:relative;z-index:1}}
.win-display.show{{opacity:1;animation:win-pop 0.4s ease}}
@keyframes win-pop{{0%{{transform:scale(0.5)}}60%{{transform:scale(1.2)}}100%{{transform:scale(1)}}}}
.controls{{display:flex;gap:12px;align-items:center;margin:12px 0;position:relative;z-index:1}}
.btn{{padding:14px 40px;border-radius:50px;border:none;font-size:16px;font-weight:700;cursor:pointer;transition:all 0.2s;font-family:inherit}}
.btn-spin{{background:linear-gradient(135deg,{color_accent},{color_accent}cc);color:#000;box-shadow:0 0 25px {color_accent}33}}
.btn-spin:hover{{transform:scale(1.05);box-shadow:0 0 35px {color_accent}55}}
.btn-spin:disabled{{opacity:0.4;transform:none;cursor:not-allowed}}
.btn-sm{{padding:8px 16px;font-size:13px;background:#ffffff15;color:{color_text};border:1px solid #ffffff22;border-radius:8px}}
.btn-sm:hover{{background:#ffffff25}}
.paytable{{display:none;position:fixed;inset:0;z-index:100;background:{color_primary}ee;padding:40px 20px;overflow-y:auto;backdrop-filter:blur(12px)}}
.paytable.show{{display:block}}
.paytable h2{{color:{color_accent};margin-bottom:16px;text-align:center}}
.paytable table{{width:100%;max-width:400px;margin:0 auto;border-collapse:collapse;font-size:14px}}
.paytable td{{padding:8px 12px;border-bottom:1px solid #ffffff15;text-align:center;vertical-align:middle}}
.paytable .sym-cell{{font-size:24px}}
.paytable .close{{position:absolute;top:16px;right:16px;font-size:24px;cursor:pointer;opacity:0.5}}
.paytable .close:hover{{opacity:1}}
.features{{max-width:400px;margin:16px auto;padding:16px;background:#ffffff08;border-radius:8px}}
.features h3{{color:{color_accent};font-size:14px;margin-bottom:8px}}
.features li{{font-size:12px;opacity:0.7;margin-left:16px;margin-bottom:4px}}
.footer{{margin-top:auto;padding:12px;text-align:center;font-size:10px;opacity:0.3;position:relative;z-index:1}}
.prototype-badge{{position:fixed;top:8px;right:8px;padding:4px 10px;background:#ff000088;color:#fff;font-size:10px;font-weight:700;border-radius:4px;z-index:200;text-transform:uppercase}}
/* ── BONUS OVERLAY ── */
#bonusOverlay{{display:none;position:fixed;inset:0;z-index:150;background:rgba(0,0,0,0.85);backdrop-filter:blur(8px);place-items:center;justify-content:center;flex-direction:column}}
#bonusOverlay.show{{display:flex}}
.bonus-content{{text-align:center;padding:40px;max-width:400px}}
.bonus-content h2{{font-size:28px;color:{color_accent};margin-bottom:16px;text-shadow:0 0 20px {color_accent}66}}
.bonus-content p{{font-size:16px;margin-bottom:12px;line-height:1.6}}
.bonus-content .bonus-prize{{font-size:32px;font-weight:800;color:{color_accent};margin:16px 0}}
.bonus-pick-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px auto;max-width:300px}}
.bonus-pick-item{{padding:20px;background:#ffffff15;border-radius:12px;font-size:24px;cursor:pointer;transition:all 0.2s;border:2px solid transparent}}
.bonus-pick-item:hover{{background:#ffffff25;border-color:{color_accent}44;transform:scale(1.05)}}
.bonus-pick-item.revealed{{cursor:default;border-color:{color_accent}}}
.bonus-wheel{{width:200px;height:200px;border-radius:50%;border:4px solid {color_accent};margin:20px auto;position:relative;transition:transform 3s cubic-bezier(0.17,0.67,0.12,0.99)}}
.free-spin-counter{{font-size:48px;font-weight:800;color:{color_accent};text-shadow:0 0 30px {color_accent}66}}
/* ── PARTICLES ── */
.particle-container{{position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden}}
.particle{{position:absolute;width:3px;height:3px;background:var(--particle-color,{color_accent});border-radius:50%;opacity:0;animation:float-up 4s ease-in infinite}}
@keyframes float-up{{0%{{opacity:0;transform:translateY(100vh) scale(0)}}10%{{opacity:0.6}}90%{{opacity:0.2}}100%{{opacity:0;transform:translateY(-20px) scale(1)}}}}
@media(max-width:768px){{.hud{{padding:8px 12px}}.hud-item .value{{font-size:15px}}.btn{{padding:12px 32px;font-size:14px}}}}

/* ── AI THEME LAYER ── */
{theme_css}
</style>
</head>
<body>
<div class="prototype-badge">PROTOTYPE</div>
<div class="particle-container" id="particles"></div>

<div class="header">
    <h1>{game_title}</h1>
    <div class="tag">{theme} &bull; {grid_cols}&times;{grid_rows} &bull; RTP {target_rtp}% &bull; {volatility.title()} Vol</div>
</div>

<div class="win-display" id="winDisplay"></div>
<div class="reel-window" id="reelWindow"></div>

<div class="hud">
    <div class="hud-item"><div class="label">Balance</div><div class="value" id="balance">1000.00</div></div>
    <div class="hud-item"><div class="label">Bet</div><div class="value" id="betDisplay">1.00</div></div>
    <div class="hud-item"><div class="label">Won</div><div class="value" id="totalWon">0.00</div></div>
</div>

<div class="controls">
    <button class="btn btn-sm" onclick="adjustBet(-0.25)">&minus;</button>
    <button class="btn btn-spin" id="spinBtn" onclick="spin()">SPIN</button>
    <button class="btn btn-sm" onclick="adjustBet(0.25)">+</button>
    <button class="btn btn-sm" onclick="togglePaytable()">PAY</button>
</div>

<div class="footer">ARKAINBRAIN &bull; {game_title} &bull; For evaluation only</div>

<div class="paytable" id="paytable">
    <span class="close" onclick="togglePaytable()">&times;</span>
    <h2>{game_title} &mdash; Paytable</h2>
    <table>
        <tr style="opacity:0.5"><td></td><td>&times;5</td><td>&times;4</td><td>&times;3</td></tr>
        {pay_rows}
    </table>
    <div class="features">
        <h3>Features</h3>
        <ul>{features_html}
            <li><strong>{bonus_name}</strong> &mdash; Land {bonus_trigger}+ scatter symbols</li>
        </ul>
    </div>
    <p style="text-align:center;font-size:11px;opacity:0.4;margin-top:16px">{paytable_summary}</p>
</div>

<div id="bonusOverlay"></div>

{audio_elements}

<script>
/* ═══════════════════════════════════════════════
   SOLID ENGINE — Battle-tested, never breaks
   ═══════════════════════════════════════════════ */
const COLS={grid_cols},ROWS={grid_rows};
const SYMBOLS=[
        {symbols_js}
];
const TOTAL_WEIGHT=SYMBOLS.reduce((s,x)=>s+x.weight,0);
const HIGH_PAY_COUNT={len(high_pay)};
const SCATTER_IDX={scatter_idx};
const BONUS_TRIGGER={bonus_trigger};

let balance=1000,bet=1,totalWon=0,spinning=false;
const grid=[];
const reelWindow=document.getElementById('reelWindow');

// Build grid cells
for(let r=0;r<ROWS;r++){{grid[r]=[];for(let c=0;c<COLS;c++){{const cell=document.createElement('div');cell.className='cell';cell.id=`cell_${{r}}_${{c}}`;reelWindow.appendChild(cell);grid[r][c]=cell}}}}

function weightedRandom(){{let r=Math.random()*TOTAL_WEIGHT,acc=0;for(const s of SYMBOLS){{acc+=s.weight;if(r<acc)return s}}return SYMBOLS[SYMBOLS.length-1]}}

function renderSymbol(cell,sym){{
    if(sym.img){{cell.innerHTML=`<img src="${{sym.img}}" alt="${{sym.sym}}">`}}
    else{{cell.textContent=sym.sym;cell.style.fontSize=sym.sym.length>2?'clamp(14px,4vw,24px)':'clamp(20px,6vw,36px)'}}
}}

function adjustBet(d){{bet=Math.max(0.25,Math.min(25,+(bet+d).toFixed(2)));document.getElementById('betDisplay').textContent=bet.toFixed(2)}}
function togglePaytable(){{document.getElementById('paytable').classList.toggle('show')}}
function updateHUD(){{document.getElementById('balance').textContent=balance.toFixed(2);document.getElementById('totalWon').textContent=totalWon.toFixed(2)}}

function showWin(amount){{
    const wd=document.getElementById('winDisplay');
    wd.textContent=`WIN ${{amount.toFixed(2)}}`;
    wd.className='win-display show';
    playSound('win');
}}

{audio_play_js}

async function spin(){{
    if(spinning||balance<bet)return;
    spinning=true;balance-=bet;updateHUD();
    document.getElementById('spinBtn').disabled=true;
    document.getElementById('winDisplay').className='win-display';
    document.getElementById('winDisplay').textContent='';
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++)grid[r][c].classList.remove('win','scatter-highlight');
    playSound('spin');

    // Spin animation
    for(let c=0;c<COLS;c++)for(let r=0;r<ROWS;r++)grid[r][c].classList.add('spinning');

    const result=[];
    for(let r=0;r<ROWS;r++){{result[r]=[];for(let c=0;c<COLS;c++)result[r][c]=weightedRandom()}}

    // Stop columns with stagger
    for(let c=0;c<COLS;c++){{
        await new Promise(res=>setTimeout(res,180+c*140));
        for(let r=0;r<ROWS;r++){{grid[r][c].classList.remove('spinning');renderSymbol(grid[r][c],result[r][c])}}
    }}

    // Check wins (left-to-right consecutive on each row)
    let totalPay=0;
    for(let r=0;r<ROWS;r++){{
        let count=1;
        for(let c=1;c<COLS;c++){{if(result[r][c].sym===result[r][0].sym)count++;else break}}
        if(count>=3){{
            const symIdx=SYMBOLS.indexOf(result[r][0]);
            const isHigh=symIdx>=0&&symIdx<HIGH_PAY_COUNT;
            const basePay=isHigh?Math.max(2,10-symIdx*2):Math.max(1,3-(symIdx-HIGH_PAY_COUNT));
            const mult=count===5?5:count===4?3:1;
            totalPay+=basePay*mult*bet;
            for(let c=0;c<count;c++)grid[r][c].classList.add('win');
        }}
    }}

    // Check scatter count for bonus trigger
    let scatterCount=0;
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){{
        if(result[r][c].isScatter){{scatterCount++;grid[r][c].classList.add('scatter-highlight')}}
    }}

    if(totalPay>0){{balance+=totalPay;totalWon+=totalPay;showWin(totalPay)}}

    // Trigger bonus round
    if(scatterCount>=BONUS_TRIGGER){{
        playSound('bonus');
        await new Promise(r=>setTimeout(r,800));
        try{{
            const bonusWin=await runBonusRound(bet,{{
                balance,totalWon,grid,COLS,ROWS,updateHUD,weightedRandom,showWin,renderSymbol,playSound
            }});
            if(typeof bonusWin==='number'&&bonusWin>0){{
                balance+=bonusWin;totalWon+=bonusWin;
                showWin(bonusWin);
            }}
        }}catch(e){{console.error('Bonus round error:',e);balance+=bet*10;totalWon+=bet*10;showWin(bet*10)}}
    }}

    updateHUD();spinning=false;document.getElementById('spinBtn').disabled=false;
}}

// Initial fill
for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++)renderSymbol(grid[r][c],weightedRandom());

// Floating particles
(function initParticles(){{
    const container=document.getElementById('particles');
    for(let i=0;i<15;i++){{
        const p=document.createElement('div');p.className='particle';
        p.style.left=Math.random()*100+'%';
        p.style.animationDelay=Math.random()*4+'s';
        p.style.animationDuration=(3+Math.random()*3)+'s';
        p.style.width=p.style.height=(2+Math.random()*3)+'px';
        container.appendChild(p);
    }}
}})();

/* ═══════════════════════════════════════════════
   AI BONUS MODULE — Custom per theme
   (wrapped in try/catch — base game works without it)
   ═══════════════════════════════════════════════ */
try {{
{bonus_js}
}} catch(e) {{
    console.warn('Bonus module failed to load, using fallback:', e);
    async function runBonusRound(bet, state) {{
        const overlay=document.getElementById('bonusOverlay');
        overlay.innerHTML='<div class="bonus-content"><h2>{bonus_name}</h2><p>Bonus! You win '+bet*15+'!</p></div>';
        overlay.classList.add('show');
        await new Promise(r=>setTimeout(r,2000));
        overlay.classList.remove('show');
        return bet*15;
    }}
}}
</script>
</body>
</html>'''

    # Save
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '_', game_title.lower())[:30]
    file_path = out_path / f"{slug}_prototype.html"
    file_path.write_text(html, encoding="utf-8")

    file_size = file_path.stat().st_size
    return json.dumps({
        "status": "success",
        "file_path": str(file_path),
        "file_size_kb": round(file_size / 1024, 1),
        "grid": f"{grid_cols}x{grid_rows}",
        "symbols_total": len(all_syms),
        "symbols_with_images": len(symbol_images),
        "has_background": bool(bg_image),
        "audio_files": len(audio_files),
        "ai_theme": bool(theme_css),
        "bonus_name": bonus_name,
        "bonus_trigger": f"{bonus_trigger}+ scatters",
        "features": features,
        "note": "AI-themed prototype with custom visuals and bonus round.",
    }, indent=2)
