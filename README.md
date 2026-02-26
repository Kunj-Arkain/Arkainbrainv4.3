# ARKAINBRAIN v4.0 — AI-Powered Gaming Intelligence Platform

Built by [ArkainGames.com](https://arkaingames.com)

## What It Does

Point ARKAINBRAIN at a game concept and target jurisdictions — it deploys a team of AI agents that research the market, design the game, simulate the math, generate art + audio, check patents, plan certification, and package everything as production-ready deliverables.

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Fill in: OPENAI_API_KEY, SERPER_API_KEY (required)
# Optional: ELEVENLABS_API_KEY, QDRANT_URL, QDRANT_API_KEY

# 3. Run (web dashboard)
python web_app.py
# → http://localhost:5000

# 4. Or run (CLI)
python main.py --theme "Ancient Egyptian" --markets Georgia Texas --volatility high
```

## Target Jurisdictions

Enter **any jurisdiction** — US states, countries, or regulated markets:
- **US States**: Georgia, Texas, North Carolina, etc. → Auto State Recon researches laws first
- **International**: UK, Malta, Ontario, Sweden, Curacao, New Jersey, Spain
- **Mix**: `Georgia, Texas, UK, Malta` works fine

Default: **Georgia, Texas**

## Pipeline Stages

```
Initialize → Pre-Flight Intel → Research → [Review] → Design + Math →
[Review] → Mood Boards → [Review] → Production + Audio → Assembly → Package
```

### Pre-Flight Intelligence
- 🛰️ Trend Radar — Is this theme rising or saturated?
- ⚖️ Jurisdiction Intersection — Computes tightest constraints across all markets
- 🔒 Patent/IP Scanner — Checks mechanics against known gaming patents
- 🧠 Knowledge Base — References past designs
- 🌐 State Recon Data — Pulls Qdrant-cached legal research for US states

### 15 Active Upgrades

| # | Upgrade | What It Does |
|---|---------|-------------|
| 1 | Deep Research | Full web page analysis, not just snippets |
| 2 | Competitor Teardown | RTP, volatility, features from real games |
| 3 | Knowledge Base | Qdrant-backed memory across pipeline runs |
| 4 | Adversarial Review | Devil's advocate at every stage |
| 5 | Web HITL | Browser-based approve/reject checkpoints |
| 6 | Vision QA | GPT-4o checks every generated image |
| 7 | Paytable Optimizer | Iterative RTP convergence to ±0.1% |
| 8 | Jurisdiction Engine | Multi-market legal intersection |
| 9 | Player Behavior | 5K session simulation, churn risk scoring |
| 10 | Agent Debate | Designer vs Mathematician negotiation |
| 11 | Trend Radar | Live market trend detection |
| 12 | Patent Scanner | Google Patents + USPTO IP conflict check |
| 13 | HTML5 Prototype | Playable browser demo, zero dependencies |
| 14 | AI Sound Design | ElevenLabs-generated game audio (13 sounds) |
| 15 | Certification Planner | Test lab, timeline, cost per market |

## API Keys

| Key | Required | Purpose |
|-----|----------|---------|
| `OPENAI_API_KEY` | Yes | GPT-4o agents + DALL-E 3 art + Vision QA |
| `SERPER_API_KEY` | Yes | Web search, patents, trends, competitors |
| `ELEVENLABS_API_KEY` | Optional | AI sound effect generation |
| `QDRANT_URL` + `QDRANT_API_KEY` | Optional | Vector DB for regulations + knowledge base |
| `GOOGLE_CLIENT_ID` + `SECRET` | For web UI | Google OAuth sign-in |

## Output Structure

```
output/{game_slug}/
├── 00_preflight/        Trend radar, jurisdiction, patents, recon
├── 01_research/         Market sweep, competitor analysis
├── 02_design/           Game Design Document (GDD)
├── 03_math/             Math model, player behavior
├── 04_art/              Symbols, backgrounds, logos, mood boards
├── 04_audio/            Sound effects + audio design brief
├── 05_legal/            Compliance report, certification plan
├── 06_pdf/              Branded PDF deliverables
├── 07_prototype/        Playable HTML5 demo
└── PACKAGE_MANIFEST.json
```

## State Recon

Separate pipeline for US state legal analysis:

```bash
python main.py --recon "North Carolina"
```

Or via web UI → State Recon page. Results are stored in Qdrant and automatically pulled by the slot pipeline when targeting that state.

## Deployment

See `RAILWAY_DEPLOY.md` for Railway or `DEPLOY_PYTHONANYWHERE.md` for PythonAnywhere.
