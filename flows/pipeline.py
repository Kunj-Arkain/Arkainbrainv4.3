"""
Automated Slot Studio - Pipeline Flows (PRODUCTION)

PHASE 2+3 WIRED:
- Real litellm model strings per agent (hybrid cost routing)
- Tool outputs parsed into structured pipeline state
- PDF generator called at assembly stage
- CostTracker logs all LLM + image spend
- Math agent receives simulation template
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from config.settings import (
    LLMConfig, PipelineConfig, RAGConfig,
    CostTracker, JURISDICTION_REQUIREMENTS,
)
from models.schemas import GameIdeaInput
from tools.custom_tools import (
    SlotDatabaseSearchTool,
    MathSimulationTool,
    ImageGenerationTool,
    RegulatoryRAGTool,
    FileWriterTool,
)
from tools.advanced_research import (
    WebFetchTool,
    DeepResearchTool,
    CompetitorTeardownTool,
    KnowledgeBaseTool,
)
from tools.tier1_upgrades import (
    VisionQATool,
    PaytableOptimizerTool,
    JurisdictionIntersectionTool,
    PlayerBehaviorModelTool,
    AgentDebateTool,
    TrendRadarTool,
)
from tools.tier2_upgrades import (
    PatentIPScannerTool,
    HTML5PrototypeTool,
    SoundDesignTool,
    CertificationPlannerTool,
)

console = Console()


# ============================================================
# Pipeline State
# ============================================================

class PipelineState(BaseModel):
    job_id: str = ""  # Web HITL needs this to pause the right pipeline
    game_idea: Optional[GameIdeaInput] = None
    game_slug: str = ""
    output_dir: str = ""

    # Tier 1 pre-flight data
    trend_radar: Optional[dict] = None
    jurisdiction_constraints: Optional[dict] = None

    market_research: Optional[dict] = None
    research_approved: bool = False

    gdd: Optional[dict] = None
    math_model: Optional[dict] = None
    optimized_rtp: Optional[float] = None
    player_behavior: Optional[dict] = None
    design_math_approved: bool = False

    mood_board: Optional[dict] = None
    mood_board_approved: bool = False
    approved_mood_board_index: int = 0
    vision_qa_results: list[dict] = Field(default_factory=list)
    art_assets: Optional[dict] = None
    compliance: Optional[dict] = None

    # Tier 2 data
    patent_scan: Optional[dict] = None
    sound_design: Optional[dict] = None
    prototype_path: str = ""
    certification_plan: Optional[dict] = None
    recon_data: Optional[dict] = None  # State recon results for US jurisdictions

    total_tokens_used: int = 0
    total_images_generated: int = 0
    estimated_cost_usd: float = 0.0
    errors: list[str] = Field(default_factory=list)
    hitl_approvals: dict[str, bool] = Field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    pdf_files: list[str] = Field(default_factory=list)


# ============================================================
# Agent Factory (PHASE 2: Real LLM wiring)
# ============================================================

def create_agents() -> dict[str, Agent]:
    """
    Build all agents with REAL litellm model strings and tools.
    UPGRADED: Deep research, web fetching, competitor teardown, knowledge base.
    """

    # Core tools
    slot_search = SlotDatabaseSearchTool()
    math_sim = MathSimulationTool()
    image_gen = ImageGenerationTool()
    reg_rag = RegulatoryRAGTool()
    file_writer = FileWriterTool()

    # Advanced tools (UPGRADES 1-4)
    web_fetch = WebFetchTool()
    deep_research = DeepResearchTool()
    competitor_teardown = CompetitorTeardownTool()
    knowledge_base = KnowledgeBaseTool()

    # Tier 1 tools (UPGRADES 6-11)
    vision_qa = VisionQATool()
    paytable_optimizer = PaytableOptimizerTool()
    jurisdiction_intersect = JurisdictionIntersectionTool()
    player_behavior = PlayerBehaviorModelTool()
    agent_debate = AgentDebateTool()
    trend_radar = TrendRadarTool()

    # Tier 2 tools (UPGRADES 12-15)
    patent_scanner = PatentIPScannerTool()
    prototype_gen = HTML5PrototypeTool()
    sound_design = SoundDesignTool()
    cert_planner = CertificationPlannerTool()

    agents = {}

    # ---- Lead Producer ----
    agents["lead_producer"] = Agent(
        role="Lead Producer & Orchestrator",
        goal=(
            "Coordinate all specialist agents, manage data flow, enforce quality gates, "
            "compile the final package. ALWAYS start by: (1) checking the knowledge base for "
            "past designs with similar themes, (2) running the trend radar to validate theme "
            "direction, (3) running jurisdiction intersection to set hard constraints for all "
            "target markets before ANY design work begins."
        ),
        backstory="Veteran slot game producer with 15+ years shipping titles at major studios. Ruthlessly efficient.",
        llm=LLMConfig.get_llm("lead_producer"),
        max_iter=5,
        verbose=True,
        allow_delegation=True,
        tools=[file_writer, knowledge_base, trend_radar, jurisdiction_intersect],
    )

    # ---- Market Analyst (UPGRADED: deep research + web fetch + competitor teardown) ----
    agents["market_analyst"] = Agent(
        role="Market Intelligence Analyst",
        goal=(
            "Conduct DEEP multi-pass market analysis. Use the deep_research tool for "
            "comprehensive market sweeps — it reads FULL web pages, not just snippets. "
            "Use competitor_teardown to extract exact RTP, volatility, max win, and feature "
            "data from top competing games. Produce structured competitive intelligence "
            "with specific numbers, not vague summaries."
        ),
        backstory=(
            "Data-driven slot market analyst who built the competitive intelligence division "
            "at a top-5 gaming studio. You don't just search — you READ full articles, "
            "EXTRACT specific numbers, and CROSS-REFERENCE sources. A 200-char snippet "
            "is not research. Your reports cite specific RTPs, hit frequencies, and feature "
            "mechanics from real games. You use deep_research for comprehensive analysis "
            "and competitor_teardown for structured game data extraction."
        ),
        llm=LLMConfig.get_llm("market_analyst"),
        max_iter=15,  # More iterations for deep research loops
        verbose=True,
        tools=[deep_research, competitor_teardown, trend_radar, web_fetch, slot_search, file_writer],
    )

    # ---- Game Designer (UPGRADED: knowledge base + competitor data) ----
    agents["game_designer"] = Agent(
        role="Senior Game Designer",
        goal=(
            "Author a comprehensive, implementable GDD with zero ambiguity. ALWAYS: "
            "(1) Search knowledge_base for past designs with similar themes. "
            "(2) Use competitor_teardown to understand exact features in competing games. "
            "(3) Run jurisdiction_intersection to know what's banned/required in target markets "
            "BEFORE proposing features. (4) Use agent_debate for any contentious design decision "
            "to pre-negotiate with the mathematician perspective. (5) Use patent_ip_scan to check "
            "ANY novel mechanic for IP conflicts before committing to it."
        ),
        backstory="Senior slot game designer with 50+ shipped titles. Balances creative vision with mathematical reality.",
        llm=LLMConfig.get_llm("game_designer"),
        max_iter=8,
        verbose=True,
        tools=[knowledge_base, competitor_teardown, jurisdiction_intersect, agent_debate, patent_scanner, file_writer],
    )

    # ---- Mathematician (UPGRADED: optimizer + behavior model + debate) ----
    agents["mathematician"] = Agent(
        role="Game Mathematician & Simulation Engineer",
        goal=(
            "Design the complete math model. Write and execute a Monte Carlo simulation. "
            "THEN use optimize_paytable to iteratively converge reel strips to exact target RTP "
            "(±0.1%). THEN use model_player_behavior to validate the player experience — "
            "catch boring games, punishing dry streaks, or insufficient bonus triggers. "
            "Use agent_debate for any design decisions that affect the math budget."
        ),
        backstory=(
            "Slot mathematician with a PhD in statistics. One-shot simulations are amateur hour — "
            "you use iterative optimization to converge on exact RTP targets. You also model "
            "player sessions because a game that hits 96.0% RTP but bores players in 50 spins "
            "is a failure. Every number backed by simulation AND behavioral modeling."
        ),
        llm=LLMConfig.get_llm("mathematician"),
        max_iter=10,
        verbose=True,
        tools=[math_sim, paytable_optimizer, player_behavior, agent_debate, file_writer],
    )

    # ---- Art Director (UPGRADED: vision QA + sound design) ----
    agents["art_director"] = Agent(
        role="Art Director, Visual & Audio Designer",
        goal=(
            "Create mood boards for approval, then generate all visual AND audio assets. "
            "CRITICAL: After generating EVERY image, use vision_qa to check quality, "
            "theme adherence, regulatory compliance, and mobile readability. If vision_qa "
            "returns FAIL, regenerate the image with adjusted prompts. "
            "Use sound_design to create the audio design brief and generate AI sound effects "
            "for all core game sounds (spin, wins, bonus triggers, ambient). "
            "Use fetch_web_page to research visual references before designing."
        ),
        backstory=(
            "Creative director for 30+ slot games covering both visual AND audio design. "
            "You NEVER ship unchecked art — every image goes through AI-powered QA. "
            "You also design the complete audio experience: from subtle reel ticks to "
            "epic mega-win fanfares. Audio is 30-40% of the player experience and you "
            "treat it with the same rigor as visual design."
        ),
        llm=LLMConfig.get_llm("art_director"),
        max_iter=15,  # More iterations: generate + QA + regenerate cycle
        verbose=True,
        tools=[image_gen, vision_qa, sound_design, web_fetch, file_writer],
    )

    # ---- Compliance Officer (UPGRADED: deep research + web fetch for live law lookup) ----
    agents["compliance_officer"] = Agent(
        role="Legal & Regulatory Compliance Officer",
        goal=(
            "Review the complete game package against regulatory requirements. "
            "Use deep_research to look up CURRENT regulations — laws change frequently. "
            "Use fetch_web_page to read the FULL TEXT of any statute or regulation. "
            "Use patent_ip_scan to check game mechanics for IP conflicts. "
            "Use certification_planner to map the full cert path: test lab, standards, "
            "timeline, cost estimate. Flag blockers, risks, and required modifications."
        ),
        backstory=(
            "Gaming compliance specialist with 100+ games guided through GLI, BMM, eCOGRA. "
            "You ALWAYS verify regulations against the actual statute text — never rely on "
            "summaries or cached data alone. You use deep_research and web_fetch to check "
            "the latest regulatory positions."
        ),
        llm=LLMConfig.get_llm("compliance_officer"),
        max_iter=8,
        verbose=True,
        tools=[reg_rag, jurisdiction_intersect, cert_planner, patent_scanner, deep_research, web_fetch, file_writer],
    )

    # ---- Adversarial Reviewer (NEW — UPGRADE 5) ----
    from agents.adversarial_reviewer import create_adversarial_reviewer
    agents["adversarial_reviewer"] = create_adversarial_reviewer()

    return agents


# ============================================================
# HITL Helper (Web + CLI)
# ============================================================

def hitl_checkpoint(name: str, summary: str, state: PipelineState, auto: bool = False) -> bool:
    """
    Human-in-the-loop checkpoint.
    - If auto=True or HITL disabled: auto-approve
    - If state.job_id is set: use web HITL (blocks until user responds in browser)
    - Otherwise: fall back to CLI prompt
    """
    if auto or not PipelineConfig.HITL_ENABLED:
        console.print(f"[dim]⏭ Auto-approved: {name}[/dim]")
        state.hitl_approvals[name] = True
        return True

    # Web-based HITL
    if state.job_id:
        try:
            from tools.web_hitl import web_hitl_checkpoint
            # Collect file paths relative to output_dir for the review UI
            files = []
            out = Path(state.output_dir)
            if out.exists():
                for f in sorted(out.rglob("*")):
                    if f.is_file():
                        files.append(str(f.relative_to(out)))

            approved, feedback = web_hitl_checkpoint(
                job_id=state.job_id,
                stage=name,
                title=name.replace("_", " ").title(),
                summary=summary,
                files=files[-20:],  # Last 20 files max
                auto=False,
                timeout=7200,  # 2 hour max wait
            )
            state.hitl_approvals[name] = approved
            if not approved and feedback:
                state.errors.append(f"HITL rejection at {name}: {feedback}")
            return approved
        except Exception as e:
            console.print(f"[yellow]Web HITL failed ({e}), falling back to CLI[/yellow]")

    # CLI fallback
    console.print(Panel(summary, title=f"🔍 HITL: {name}", border_style="yellow"))
    approved = Confirm.ask("[bold yellow]Approve?[/bold yellow]", default=True)
    state.hitl_approvals[name] = approved
    if not approved:
        fb = Prompt.ask("[yellow]Feedback (or 'skip' to abort)[/yellow]")
        if fb.lower() != "skip":
            state.errors.append(f"HITL rejection at {name}: {fb}")
    return approved


# ============================================================
# Simulation Template Loader
# ============================================================

def load_simulation_template() -> str:
    """Load the base Monte Carlo simulation template for the Math agent."""
    template_path = Path(__file__).parent.parent / "templates" / "math_simulation.py"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "# Simulation template not found — write from scratch"


# ============================================================
# Main Pipeline Flow
# ============================================================

class SlotStudioFlow(Flow[PipelineState]):

    def __init__(self, auto_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.auto_mode = auto_mode
        self.agents = create_agents()
        self.cost_tracker = CostTracker()

    # ---- Stage 1: Initialize ----

    @start()
    def initialize(self):
        console.print(Panel(
            f"[bold]🎰 Automated Slot Studio[/bold]\n\n"
            f"Theme: {self.state.game_idea.theme}\n"
            f"Markets: {', '.join(self.state.game_idea.target_markets)}\n"
            f"Volatility: {self.state.game_idea.volatility.value}\n"
            f"RTP: {self.state.game_idea.target_rtp}% | Max Win: {self.state.game_idea.max_win_multiplier}x\n\n"
            f"LLM Routing:\n"
            f"  Heavy (Designer/Math/Legal): {LLMConfig.HEAVY}\n"
            f"  Light (Analyst/Art):         {LLMConfig.LIGHT}",
            title="Pipeline Starting", border_style="green",
        ))
        self.state.started_at = datetime.now().isoformat()
        slug = "".join(c if c.isalnum() else "_" for c in self.state.game_idea.theme.lower())[:40]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.state.game_slug = f"{slug}_{ts}"
        self.state.output_dir = str(Path(os.getenv("OUTPUT_DIR", "./output")) / self.state.game_slug)
        for sub in ["00_preflight", "01_research", "02_design", "03_math", "04_art/mood_boards",
                     "04_art/symbols", "04_art/backgrounds", "04_art/ui",
                     "04_audio", "05_legal", "06_pdf", "07_prototype"]:
            Path(self.state.output_dir, sub).mkdir(parents=True, exist_ok=True)
        console.print(f"[green]📁 Output: {self.state.output_dir}[/green]")

    # ---- Stage 2: Pre-Flight Intelligence ----

    @listen(initialize)
    def run_preflight(self):
        console.print("\n[bold cyan]🛰️ Stage 0: Pre-Flight Intelligence[/bold cyan]\n")
        idea = self.state.game_idea

        # A) Trend Radar — is this theme trending up or saturated?
        try:
            console.print("[cyan]📡 Running trend radar...[/cyan]")
            radar = TrendRadarTool()
            radar_result = json.loads(radar._run(
                focus="all",
                timeframe="6months",
                theme_filter=idea.theme.split()[0] if idea.theme else "",
            ))
            self.state.trend_radar = radar_result
            Path(self.state.output_dir, "00_preflight", "trend_radar.json").parent.mkdir(parents=True, exist_ok=True)
            Path(self.state.output_dir, "00_preflight", "trend_radar.json").write_text(
                json.dumps(radar_result, indent=2), encoding="utf-8"
            )
            console.print("[green]✅ Trend radar complete[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Trend radar failed (non-fatal): {e}[/yellow]")

        # B) Jurisdiction Intersection — hard constraints for all target markets
        try:
            console.print("[cyan]⚖️ Computing jurisdiction intersection...[/cyan]")
            jx = JurisdictionIntersectionTool()
            jx_result = json.loads(jx._run(
                markets=idea.target_markets,
                proposed_rtp=idea.target_rtp,
                proposed_features=[f.value for f in idea.requested_features],
                proposed_max_win=idea.max_win_multiplier,
            ))
            self.state.jurisdiction_constraints = jx_result
            Path(self.state.output_dir, "00_preflight", "jurisdiction_constraints.json").write_text(
                json.dumps(jx_result, indent=2), encoding="utf-8"
            )

            # Check for blockers
            blockers = jx_result.get("intersection", {}).get("blockers", [])
            if blockers:
                console.print(f"[bold red]🚨 BLOCKERS FOUND: {blockers}[/bold red]")
                self.state.errors.extend(blockers)
            else:
                console.print("[green]✅ All markets clear — no blockers[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Jurisdiction check failed (non-fatal): {e}[/yellow]")

        # C) Knowledge Base — learn from past designs
        try:
            console.print("[cyan]🧠 Checking knowledge base for past designs...[/cyan]")
            kb = KnowledgeBaseTool()
            kb_result = json.loads(kb._run(action="search", query=f"{idea.theme} {idea.volatility.value} slot game"))
            if kb_result.get("results_count", 0) > 0:
                Path(self.state.output_dir, "00_preflight", "past_designs.json").write_text(
                    json.dumps(kb_result, indent=2), encoding="utf-8"
                )
                console.print(f"[green]✅ Found {kb_result['results_count']} past designs to reference[/green]")
            else:
                console.print("[dim]No past designs found — this is a fresh concept[/dim]")
        except Exception as e:
            console.print(f"[dim]Knowledge base not available: {e}[/dim]")

        # D) Patent / IP Scan — check proposed mechanics for conflicts
        try:
            console.print("[cyan]🔍 Scanning for patent/IP conflicts...[/cyan]")
            scanner = PatentIPScannerTool()
            # Build mechanic description from features
            features_desc = ", ".join(f.value.replace("_", " ") for f in idea.requested_features)
            scan_result = json.loads(scanner._run(
                mechanic_description=f"{features_desc} slot game mechanic",
                keywords=[f.value.replace("_", " ") for f in idea.requested_features],
                theme_name=idea.theme,
            ))
            self.state.patent_scan = scan_result
            Path(self.state.output_dir, "00_preflight", "patent_scan.json").write_text(
                json.dumps(scan_result, indent=2), encoding="utf-8"
            )
            risk = scan_result.get("risk_assessment", {}).get("overall_ip_risk", "UNKNOWN")
            if risk == "HIGH":
                console.print(f"[bold red]🚨 HIGH IP RISK: {scan_result.get('recommendations', [])}[/bold red]")
            else:
                console.print(f"[green]✅ Patent scan complete — risk level: {risk}[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Patent scan failed (non-fatal): {e}[/yellow]")

        # E) State Recon Data — pull any cached recon results for US state markets
        try:
            from tools.qdrant_store import JurisdictionStore
            store = JurisdictionStore()
            for market in idea.target_markets:
                results = store.search(f"{market} gambling law requirements", jurisdiction=market, limit=3)
                if results and "error" not in results[0]:
                    console.print(f"[green]✅ Found recon data for {market} in Qdrant[/green]")
                    recon_path = Path(self.state.output_dir, "00_preflight", f"recon_{market.lower().replace(' ', '_')}.json")
                    recon_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            console.print(f"[dim]Qdrant recon lookup skipped: {e}[/dim]")

    # ---- Stage 2b: Research ----

    @listen(run_preflight)
    def run_research(self):
        console.print("\n[bold blue]📊 Stage 1: Market Research[/bold blue]\n")
        idea = self.state.game_idea

        # Pre-flight context for research agents
        preflight_ctx = ""
        if self.state.trend_radar:
            top_themes = self.state.trend_radar.get("trending_themes", [])[:5]
            preflight_ctx += f"\nTREND RADAR: Top themes = {json.dumps(top_themes)}\n"
            if self.state.trend_radar.get("theme_analysis"):
                preflight_ctx += f"Theme analysis: {json.dumps(self.state.trend_radar['theme_analysis'])}\n"
        if self.state.jurisdiction_constraints:
            jx = self.state.jurisdiction_constraints.get("intersection", {})
            preflight_ctx += f"\nJURISDICTION CONSTRAINTS:\n"
            preflight_ctx += f"  RTP floor: {jx.get('rtp_floor', 'unknown')}%\n"
            preflight_ctx += f"  Banned features: {jx.get('banned_features', {})}\n"
            preflight_ctx += f"  Required features: {jx.get('required_features_union', [])}\n"
            preflight_ctx += f"  Blockers: {jx.get('blockers', [])}\n"
        if self.state.patent_scan:
            risk = self.state.patent_scan.get("risk_assessment", {})
            preflight_ctx += f"\nPATENT SCAN:\n"
            preflight_ctx += f"  Overall IP risk: {risk.get('overall_ip_risk', 'unknown')}\n"
            preflight_ctx += f"  Known patent hits: {self.state.patent_scan.get('known_patent_hits', [])}\n"
            preflight_ctx += f"  Recommendations: {self.state.patent_scan.get('recommendations', [])}\n"

        sweep_task = Task(
            description=(
                f"Conduct a BROAD market sweep for the theme '{idea.theme}'.\n"
                f"Search for up to {PipelineConfig.COMPETITOR_BROAD_SWEEP_LIMIT} existing games.\n"
                f"Categorize saturation level. Find underserved angles.\n"
                f"{preflight_ctx}\n"
                f"Use the trend_radar and deep_research tools for comprehensive analysis.\n"
                f"Output a JSON object with keys: theme_keyword, total_games_found, "
                f"saturation_level, top_providers, dominant_mechanics, underserved_angles, "
                f"trending_direction, theme_trajectory (rising/stable/declining)."
            ),
            expected_output="JSON market saturation analysis",
            agent=self.agents["market_analyst"],
        )

        dive_task = Task(
            description=(
                f"Deep-dive on top {PipelineConfig.COMPETITOR_DEEP_DIVE_LIMIT} competitors "
                f"plus references: {', '.join(idea.competitor_references)}.\n"
                f"For each: provider, RTP, volatility, max win, features, player sentiment.\n"
                f"Synthesize differentiation strategy: primary_differentiator, mechanic_opportunities, "
                f"theme_twist, visual_differentiation, player_pain_points.\n"
                f"Output as JSON."
            ),
            expected_output="JSON competitor analysis + differentiation strategy",
            agent=self.agents["market_analyst"],
            context=[sweep_task],
        )

        crew = Crew(
            agents=[self.agents["market_analyst"]],
            tasks=[sweep_task, dive_task],
            process=Process.sequential, verbose=True,
        )
        result = crew.kickoff()

        self.state.market_research = {
            "sweep": str(sweep_task.output),
            "deep_dive": str(dive_task.output),
            "raw": str(result),
        }
        Path(self.state.output_dir, "01_research", "market_research.json").write_text(
            json.dumps(self.state.market_research, indent=2, default=str), encoding="utf-8"
        )
        console.print("[green]✅ Research complete[/green]")

    @listen(run_research)
    def checkpoint_research(self):
        # Run adversarial review before HITL
        self._run_adversarial_review("post_research",
            f"Theme: {self.state.game_idea.theme}\n"
            f"Market Research Output: {json.dumps(self.state.market_research, default=str)[:3000]}")

        self.state.research_approved = hitl_checkpoint(
            "post_research",
            f"Research complete for '{self.state.game_idea.theme}'.\n"
            f"See: {self.state.output_dir}/01_research/\n"
            f"Adversarial review: {self.state.output_dir}/adversarial_review_post_research.md",
            self.state, auto=self.auto_mode,
        )

    # ---- Stage 3: Design + Math ----

    @listen(checkpoint_research)
    def run_design_and_math(self):
        if not self.state.research_approved:
            return
        console.print("\n[bold yellow]📄 Stage 2: Design & Math[/bold yellow]\n")
        idea = self.state.game_idea
        market_ctx = json.dumps(self.state.market_research, default=str)[:5000]
        sim_template = load_simulation_template()

        gdd_task = Task(
            description=(
                f"Write the complete Game Design Document.\n\n"
                f"Theme: {idea.theme} | Grid: {idea.grid_cols}x{idea.grid_rows}, {idea.ways_or_lines}\n"
                f"Volatility: {idea.volatility.value} | RTP: {idea.target_rtp}% | Max Win: {idea.max_win_multiplier}x\n"
                f"Features: {[f.value for f in idea.requested_features]}\n"
                f"Art Style: {idea.art_style}\n\n"
                f"MARKET CONTEXT:\n{market_ctx}\n\n"
                f"Include: 5 high-pay symbols, 4 low-pay, Wild, Scatter with pay values.\n"
                f"Feature specs with trigger conditions and RTP contribution.\n"
                f"Audio direction, UI/UX notes, differentiation strategy.\n\n"
                f"Save the full GDD to: {self.state.output_dir}/02_design/gdd.md"
            ),
            expected_output="Complete Game Design Document saved to file",
            agent=self.agents["game_designer"],
        )

        math_task = Task(
            description=(
                f"Build the mathematical model for this slot game.\n\n"
                f"Grid: {idea.grid_cols}x{idea.grid_rows}, {idea.ways_or_lines}\n"
                f"Target RTP: {idea.target_rtp}% | Volatility: {idea.volatility.value}\n"
                f"Max Win: {idea.max_win_multiplier}x | Markets: {idea.target_markets}\n\n"
                f"Use the GDD's symbol and feature specifications.\n\n"
                f"HERE IS A SIMULATION TEMPLATE to customize:\n```python\n{sim_template[:3000]}\n```\n\n"
                f"DELIVERABLES — FOLLOW THIS SEQUENCE:\n"
                f"1. Design initial reel strips\n"
                f"2. Execute a {PipelineConfig.SIMULATION_SPINS:,}-spin Monte Carlo simulation\n"
                f"3. Use optimize_paytable to iteratively converge to exact {idea.target_rtp}% RTP (±0.1%)\n"
                f"4. Use model_player_behavior to validate the player experience:\n"
                f"   - Session length, dry streaks, bonus trigger rate, engagement score\n"
                f"   - If churn_risk is CRITICAL or HIGH, adjust hit frequency or bonus trigger rate\n"
                f"5. Use agent_debate if any feature affects the RTP budget significantly\n"
                f"6. Report: final RTP, hit frequency, volatility index, win distribution, behavior metrics\n\n"
                f"Use the run_math_simulation tool to execute your Python code.\n"
                f"Save reel strips to: {self.state.output_dir}/03_math/reel_strips.csv\n"
                f"Save simulation results to: {self.state.output_dir}/03_math/simulation_results.json\n"
                f"Save player behavior report to: {self.state.output_dir}/03_math/player_behavior.json\n\n"
                f"CRITICAL: If RTP deviates >0.5% from target, use optimize_paytable. "
                f"If player behavior shows CRITICAL churn risk, adjust and re-simulate."
            ),
            expected_output="Math model with simulation results saved to files",
            agent=self.agents["mathematician"],
            context=[gdd_task],
        )

        crew = Crew(
            agents=[self.agents["game_designer"], self.agents["mathematician"]],
            tasks=[gdd_task, math_task],
            process=Process.sequential, verbose=True,
        )
        result = crew.kickoff()

        self.state.gdd = {"output": str(gdd_task.output)}
        self.state.math_model = {"output": str(math_task.output)}

        # Try to load simulation results if the math agent saved them
        sim_path = Path(self.state.output_dir, "03_math", "simulation_results.json")
        if sim_path.exists():
            try:
                self.state.math_model["results"] = json.loads(sim_path.read_text())
            except json.JSONDecodeError:
                pass

        console.print("[green]✅ GDD + Math complete[/green]")

    @listen(run_design_and_math)
    def checkpoint_design(self):
        if not self.state.research_approved:
            return
        # Adversarial review of GDD + Math
        self._run_adversarial_review("post_design_math",
            f"Theme: {self.state.game_idea.theme}\n"
            f"Markets: {self.state.game_idea.target_markets}\n"
            f"GDD: {str(self.state.gdd.get('output',''))[:2000]}\n"
            f"Math: {str(self.state.math_model.get('output',''))[:2000]}")

        self.state.design_math_approved = hitl_checkpoint(
            "post_design_math",
            f"GDD + Math complete. This is the CRITICAL checkpoint.\n"
            f"GDD: {self.state.output_dir}/02_design/\nMath: {self.state.output_dir}/03_math/\n"
            f"Adversarial review: {self.state.output_dir}/adversarial_review_post_design_math.md",
            self.state, auto=self.auto_mode,
        )

    # ---- Stage 4: Mood Boards ----

    @listen(checkpoint_design)
    def run_mood_boards(self):
        if not self.state.design_math_approved:
            return
        console.print("\n[bold magenta]🎨 Stage 3a: Mood Boards[/bold magenta]\n")
        idea = self.state.game_idea
        mood_task = Task(
            description=(
                f"Create {PipelineConfig.MOOD_BOARD_VARIANTS} mood board variants for '{idea.theme}'.\n"
                f"Style: {idea.art_style}\n\n"
                f"For each variant: define style direction, color palette (6-8 hex codes), mood keywords.\n"
                f"Use the generate_image tool to create a concept image for each variant.\n"
                f"CRITICAL: After EACH image, use vision_qa to check quality:\n"
                f"  - Theme adherence, distinctiveness, scalability, emotional impact\n"
                f"  - If vision_qa returns FAIL, adjust the prompt and regenerate\n"
                f"Save images to: {self.state.output_dir}/04_art/mood_boards/\n"
                f"Save QA results to: {self.state.output_dir}/04_art/mood_boards/qa_report.json\n"
                f"Recommend the best variant for differentiation."
            ),
            expected_output="Mood board variants with images saved",
            agent=self.agents["art_director"],
        )
        crew = Crew(agents=[self.agents["art_director"]], tasks=[mood_task], process=Process.sequential, verbose=True)
        result = crew.kickoff()
        self.state.mood_board = {"output": str(result)}
        console.print("[green]✅ Mood boards generated[/green]")

    @listen(run_mood_boards)
    def checkpoint_art(self):
        if not self.state.design_math_approved:
            return
        # Adversarial review of art
        self._run_adversarial_review("post_art_review",
            f"Theme: {self.state.game_idea.theme}\n"
            f"Art Style: {self.state.game_idea.art_style}\n"
            f"Mood Board Output: {str(self.state.mood_board.get('output',''))[:2000]}")

        self.state.mood_board_approved = hitl_checkpoint(
            "post_art_review",
            f"Mood boards in: {self.state.output_dir}/04_art/mood_boards/\n"
            f"Adversarial review: {self.state.output_dir}/adversarial_review_post_art_review.md\n"
            f"Select preferred direction.",
            self.state, auto=self.auto_mode,
        )

    # ---- Stage 5: Full Production ----

    @listen(checkpoint_art)
    def run_production(self):
        if not self.state.mood_board_approved:
            return
        console.print("\n[bold magenta]🎨⚖️ Stage 3b: Production + Compliance[/bold magenta]\n")
        idea = self.state.game_idea
        gdd_ctx = str(self.state.gdd.get("output", ""))[:5000]
        math_ctx = str(self.state.math_model.get("output", ""))[:3000]

        art_task = Task(
            description=(
                f"Generate all visual assets for '{idea.theme}' using the approved mood board.\n\n"
                f"GDD context:\n{gdd_ctx}\n\n"
                f"Generate with the generate_image tool:\n"
                f"1. Each symbol (high-pay, low-pay, wild, scatter)\n"
                f"2. Base game background\n3. Feature background\n4. Game logo\n\n"
                f"CRITICAL: After EACH image, use vision_qa to check:\n"
                f"  - Symbols: distinguishability at 64px, color contrast, theme match\n"
                f"  - Backgrounds: readability, mobile crop, UI overlay compatibility\n"
                f"  - Logo: legibility, scalability, brand impact\n"
                f"  - ALL: UK ASA compliance (no minor appeal)\n"
                f"If vision_qa returns FAIL, regenerate with adjusted prompts.\n\n"
                f"THEN generate the complete audio package:\n"
                f"  Use sound_design with action='full' to create:\n"
                f"  - Audio design brief document\n"
                f"  - AI-generated sound effects for all core sounds\n"
                f"  Save audio to: {self.state.output_dir}/04_audio/\n\n"
                f"Save art to: {self.state.output_dir}/04_art/"
            ),
            expected_output="All art + audio assets generated and saved",
            agent=self.agents["art_director"],
        )

        compliance_task = Task(
            description=(
                f"Review game package for compliance.\n\n"
                f"Target jurisdictions: {idea.target_markets}\n"
                f"GDD:\n{gdd_ctx}\nMath:\n{math_ctx}\n\n"
                f"STEP 1 — COMPLIANCE REVIEW:\n"
                f"Check: RTP compliance, content review, responsible gambling features, "
                f"IP risk for theme '{idea.theme}', feature legality per market.\n"
                f"Use the search_regulations tool for regulatory requirements.\n"
                f"Use patent_ip_scan to check ALL proposed mechanics for IP conflicts.\n\n"
                f"STEP 2 — CERTIFICATION PATH:\n"
                f"Use certification_planner to map the full cert journey:\n"
                f"  - Recommended test lab, applicable standards\n"
                f"  - Timeline and cost estimate per market\n"
                f"  - Submission documentation checklist\n"
                f"Save cert plan to: {self.state.output_dir}/05_legal/certification_plan.json\n\n"
                f"STEP 3 — FINAL REPORT:\n"
                f"Output a structured JSON compliance report with keys:\n"
                f"overall_status (green/yellow/red), flags (list), ip_assessment, "
                f"certification_path, patent_risks, jurisdiction_summary.\n\n"
                f"Save to: {self.state.output_dir}/05_legal/compliance_report.json"
            ),
            expected_output="Compliance report + certification plan saved",
            agent=self.agents["compliance_officer"],
        )

        crew = Crew(
            agents=[self.agents["art_director"], self.agents["compliance_officer"]],
            tasks=[art_task, compliance_task],
            process=Process.sequential, verbose=True,
        )
        result = crew.kickoff()
        self.state.art_assets = {"output": str(art_task.output)}
        self.state.compliance = {"output": str(compliance_task.output)}

        # Try to load structured compliance results
        comp_path = Path(self.state.output_dir, "05_legal", "compliance_report.json")
        if comp_path.exists():
            try:
                self.state.compliance["results"] = json.loads(comp_path.read_text())
            except json.JSONDecodeError:
                pass

        # Try to load cert plan
        cert_path = Path(self.state.output_dir, "05_legal", "certification_plan.json")
        if cert_path.exists():
            try:
                self.state.certification_plan = json.loads(cert_path.read_text())
            except json.JSONDecodeError:
                pass

        # Check for generated audio
        audio_dir = Path(self.state.output_dir, "04_audio")
        audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
        if audio_files:
            self.state.sound_design = {"files_count": len(audio_files), "path": str(audio_dir)}
            console.print(f"[green]🔊 {len(audio_files)} audio files generated[/green]")

        console.print("[green]✅ Production + Compliance complete[/green]")

    # ---- Stage 6: Assembly + PDF Generation ----

    @listen(run_production)
    def assemble_package(self):
        if not self.state.mood_board_approved:
            return
        console.print("\n[bold green]📦 Stage 4: Assembly + PDF Generation[/bold green]\n")

        output_path = Path(self.state.output_dir)
        pdf_dir = output_path / "06_pdf"

        # ---- Generate HTML5 Prototype ----
        try:
            console.print("[cyan]🎮 Generating AI-themed HTML5 prototype...[/cyan]")
            proto = HTML5PrototypeTool()
            idea = self.state.game_idea

            # Extract symbols from GDD if available
            symbols = ["👑", "💎", "🏆", "🌟", "A", "K", "Q", "J", "10"]
            features = [f.value.replace("_", " ").title() for f in idea.requested_features]

            # Gather context from earlier pipeline stages
            gdd_ctx = str(self.state.gdd.get("output", ""))[:3000] if self.state.gdd else ""
            math_ctx = str(self.state.math_model.get("output", ""))[:2000] if self.state.math_model else ""
            art_dir = str(output_path / "04_art")
            audio_dir = str(output_path / "04_audio")

            proto_result = json.loads(proto._run(
                game_title=idea.theme,
                theme=idea.theme,
                grid_cols=idea.grid_cols,
                grid_rows=idea.grid_rows,
                symbols=symbols,
                features=features,
                target_rtp=idea.target_rtp,
                output_dir=str(output_path / "07_prototype"),
                paytable_summary=f"Target RTP: {idea.target_rtp}% | Volatility: {idea.volatility.value} | Max Win: {idea.max_win_multiplier}x",
                art_dir=art_dir,
                audio_dir=audio_dir,
                gdd_context=gdd_ctx,
                math_context=math_ctx,
                volatility=idea.volatility.value,
                max_win_multiplier=idea.max_win_multiplier,
            ))
            self.state.prototype_path = proto_result.get("file_path", "")
            sym_imgs = proto_result.get("symbols_with_images", 0)
            bonus = proto_result.get("bonus_name", "")
            console.print(f"[green]✅ Prototype generated: {proto_result.get('file_path', '')}[/green]")
            console.print(f"    Symbols with DALL-E art: {sym_imgs} | Bonus: {bonus}")
        except Exception as e:
            console.print(f"[yellow]⚠️ Prototype generation failed (non-fatal): {e}[/yellow]")

        # ---- Generate PDFs ----
        try:
            from tools.pdf_generator import generate_full_package

            # Build params dict for PDF generator
            game_params = {
                "theme": self.state.game_idea.theme,
                "volatility": self.state.game_idea.volatility.value,
                "target_rtp": self.state.game_idea.target_rtp,
                "grid": f"{self.state.game_idea.grid_cols}x{self.state.game_idea.grid_rows}",
                "ways": self.state.game_idea.ways_or_lines,
                "max_win": self.state.game_idea.max_win_multiplier,
                "markets": ", ".join(self.state.game_idea.target_markets),
                "art_style": self.state.game_idea.art_style,
                "features": [f.value for f in self.state.game_idea.requested_features],
            }

            # Try to extract structured data for PDFs
            gdd_data = self.state.gdd.get("results", self.state.gdd) if self.state.gdd else None
            math_data = self.state.math_model.get("results", self.state.math_model) if self.state.math_model else None
            compliance_data = self.state.compliance.get("results", None) if self.state.compliance else None

            pdf_files = generate_full_package(
                output_dir=str(pdf_dir),
                game_title=self.state.game_idea.theme,
                game_params=game_params,
                research_data=self.state.market_research,
                gdd_data=gdd_data,
                math_data=math_data,
                compliance_data=compliance_data,
            )
            self.state.pdf_files = pdf_files
            console.print(f"[green]📄 Generated {len(pdf_files)} PDFs[/green]")

        except Exception as e:
            console.print(f"[yellow]⚠️ PDF generation error: {e}[/yellow]")
            self.state.errors.append(f"PDF generation failed: {e}")

        # ---- Build Manifest ----
        all_files = [str(f.relative_to(output_path)) for f in output_path.rglob("*") if f.is_file()]
        image_count = len([f for f in output_path.rglob("*") if f.suffix in (".png", ".jpg", ".webp")])

        cost_summary = self.cost_tracker.summary()

        manifest = {
            "game_title": self.state.game_idea.theme,
            "game_slug": self.state.game_slug,
            "generated_at": datetime.now().isoformat(),
            "pipeline_version": "4.0.0",  # Tier 2 upgrades
            "llm_routing": {
                "heavy_model": LLMConfig.HEAVY,
                "light_model": LLMConfig.LIGHT,
            },
            "preflight": {
                "trend_radar": bool(self.state.trend_radar),
                "jurisdiction_constraints": bool(self.state.jurisdiction_constraints),
                "blockers": self.state.jurisdiction_constraints.get("intersection", {}).get("blockers", []) if self.state.jurisdiction_constraints else [],
            },
            "math_quality": {
                "optimized_rtp": self.state.optimized_rtp,
                "player_behavior": bool(self.state.player_behavior),
                "vision_qa_checks": len(self.state.vision_qa_results),
            },
            "tier2": {
                "patent_scan": bool(self.state.patent_scan),
                "sound_design": bool(self.state.sound_design),
                "prototype": bool(self.state.prototype_path),
                "certification_plan": bool(self.state.certification_plan),
            },
            "cost": cost_summary,
            "input_parameters": self.state.game_idea.model_dump(),
            "files_generated": all_files,
            "pdf_files": self.state.pdf_files,
            "total_files": len(all_files),
            "total_images": image_count,
            "hitl_approvals": self.state.hitl_approvals,
            "errors": self.state.errors,
            "started_at": self.state.started_at,
            "completed_at": datetime.now().isoformat(),
        }

        (output_path / "PACKAGE_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf-8"
        )

        self.state.completed_at = datetime.now().isoformat()
        self.state.total_tokens_used = cost_summary["total_tokens"]
        self.state.estimated_cost_usd = cost_summary["estimated_cost_usd"]

        audio_count = len([f for f in output_path.rglob("*") if f.suffix in (".mp3", ".wav")])

        console.print(Panel(
            f"[bold green]✅ Pipeline Complete[/bold green]\n\n"
            f"📁 Output: {self.state.output_dir}\n"
            f"📄 PDFs: {len(self.state.pdf_files)}\n"
            f"🖼️ Images: {image_count}\n"
            f"🔊 Audio: {audio_count}\n"
            f"🎮 Prototype: {'Yes' if self.state.prototype_path else 'No'}\n"
            f"📊 Files: {len(all_files)}\n"
            f"💰 Est. Cost: ${cost_summary['estimated_cost_usd']:.2f}\n"
            f"⏱️ {self.state.started_at} → {self.state.completed_at}",
            title="🎰 Package Complete", border_style="green",
        ))

        # ---- Save to Knowledge Base (UPGRADE 4) ----
        try:
            from tools.advanced_research import KnowledgeBaseTool
            kb = KnowledgeBaseTool()
            game_data = {
                "theme": self.state.game_idea.theme,
                "target_markets": self.state.game_idea.target_markets,
                "volatility": self.state.game_idea.volatility.value,
                "target_rtp": self.state.game_idea.target_rtp,
                "grid": f"{self.state.game_idea.grid_cols}x{self.state.game_idea.grid_rows}",
                "ways_or_lines": self.state.game_idea.ways_or_lines,
                "max_win": self.state.game_idea.max_win_multiplier,
                "art_style": self.state.game_idea.art_style,
                "features": [f.value for f in self.state.game_idea.requested_features],
                "gdd_summary": str(self.state.gdd.get("output", ""))[:2000] if self.state.gdd else "",
                "math_summary": str(self.state.math_model.get("output", ""))[:1000] if self.state.math_model else "",
                "compliance_summary": str(self.state.compliance.get("output", ""))[:1000] if self.state.compliance else "",
                "cost_usd": cost_summary['estimated_cost_usd'],
                "completed_at": self.state.completed_at,
            }
            kb._run(action="save", game_slug=self.state.game_slug, game_data=json.dumps(game_data))
            console.print("[green]🧠 Saved to knowledge base for future reference[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Knowledge base save failed (non-fatal): {e}[/yellow]")

        return self.state

    # ============================================================
    # Adversarial Review Helper (UPGRADE 5)
    # ============================================================

    def _run_adversarial_review(self, stage: str, context_summary: str):
        """Run the adversarial reviewer agent on the current stage's output."""
        try:
            from agents.adversarial_reviewer import build_review_task_description
            console.print(f"\n[bold red]🔴 Adversarial Review: {stage}[/bold red]\n")

            review_desc = build_review_task_description(
                stage=stage,
                context_summary=context_summary,
                output_dir=self.state.output_dir,
            )

            review_task = Task(
                description=review_desc,
                expected_output=f"Structured adversarial critique saved to {self.state.output_dir}/adversarial_review_{stage}.md",
                agent=self.agents["adversarial_reviewer"],
            )

            crew = Crew(
                agents=[self.agents["adversarial_reviewer"]],
                tasks=[review_task],
                process=Process.sequential, verbose=True,
            )
            result = crew.kickoff()

            # Ensure the review is saved
            review_path = Path(self.state.output_dir, f"adversarial_review_{stage}.md")
            if not review_path.exists():
                review_path.write_text(str(result), encoding="utf-8")

            console.print(f"[green]✅ Adversarial review complete: {review_path.name}[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Adversarial review failed (non-fatal): {e}[/yellow]")
