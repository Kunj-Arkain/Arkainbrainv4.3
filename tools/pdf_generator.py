"""
Automated Slot Studio — PDF Package Generator

Produces branded Arkain Games PDF output for every pipeline deliverable:
  - Executive Summary (1-pager)
  - Market Research & Competitor Analysis
  - Game Design Document (GDD)
  - Math Model Report (with simulation charts)
  - Art Direction Brief
  - Legal & Compliance Report
  - Full Combined Package

Uses ReportLab for generation + matplotlib for charts.
All PDFs are Arkain-branded: dark headers, gold accents, consistent typography.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image,
    KeepTogether, HRFlowable,
)
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor


# ============================================================
# Arkain Brand Constants
# ============================================================

class ArkainBrand:
    """Brand colors and styling constants matching arkaingames.com."""

    # Primary palette
    BG_DARK = HexColor("#060610")
    SURFACE = HexColor("#0c0c1d")
    CARD = HexColor("#111128")

    # Accent colors
    INDIGO = HexColor("#4f46e5")
    INDIGO_LIGHT = HexColor("#6366f1")
    GOLD = HexColor("#d4a853")
    GOLD_DARK = HexColor("#a88a3d")

    # Status colors
    SUCCESS = HexColor("#22c55e")
    WARNING = HexColor("#eab308")
    DANGER = HexColor("#ef4444")

    # Text colors
    TEXT_PRIMARY = HexColor("#e8e6f0")
    TEXT_MUTED = HexColor("#7a7898")
    TEXT_DIM = HexColor("#4a4870")

    # PDF-specific (light background for readability when printed)
    PAGE_BG = HexColor("#ffffff")
    HEADER_BG = HexColor("#0c0c1d")
    SECTION_BG = HexColor("#f4f3f8")
    TABLE_HEADER_BG = HexColor("#111128")
    TABLE_ALT_ROW = HexColor("#f8f7fc")
    TEXT_DARK = HexColor("#1a1a2e")
    TEXT_BODY = HexColor("#333355")
    BORDER = HexColor("#d4d2e0")

    # Fonts
    FONT_HEADING = "Helvetica-Bold"
    FONT_BODY = "Helvetica"
    FONT_MONO = "Courier"

    # Company info
    COMPANY = "Arkain Games India Pvt. Ltd."
    TAGLINE = "Built to Play"
    CONFIDENTIAL = "CONFIDENTIAL — Internal Use Only"


# ============================================================
# Custom Page Templates
# ============================================================

def arkain_header_footer(canvas_obj, doc):
    """Draw Arkain-branded header and footer on each page."""
    canvas_obj.saveState()
    width, height = letter

    # --- Header bar ---
    canvas_obj.setFillColor(ArkainBrand.HEADER_BG)
    canvas_obj.rect(0, height - 50, width, 50, fill=1, stroke=0)

    # Gold accent line
    canvas_obj.setStrokeColor(ArkainBrand.GOLD)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(0, height - 50, width, height - 50)

    # Company name in header
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont(ArkainBrand.FONT_HEADING, 11)
    canvas_obj.drawString(30, height - 34, "ARKAIN")
    canvas_obj.setFillColor(ArkainBrand.GOLD)
    canvas_obj.drawString(78, height - 34, "STUDIO")

    # Document title in header (right side)
    canvas_obj.setFillColor(ArkainBrand.TEXT_MUTED)
    canvas_obj.setFont(ArkainBrand.FONT_BODY, 8)
    title = getattr(doc, '_arkain_title', 'Slot Game Package')
    canvas_obj.drawRightString(width - 30, height - 34, title.upper())

    # --- Footer ---
    canvas_obj.setFillColor(ArkainBrand.BORDER)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(30, 40, width - 30, 40)

    canvas_obj.setFillColor(ArkainBrand.TEXT_DIM)
    canvas_obj.setFont(ArkainBrand.FONT_BODY, 7)
    canvas_obj.drawString(30, 28, ArkainBrand.CONFIDENTIAL)
    canvas_obj.drawString(30, 18, f"Generated {datetime.now().strftime('%B %d, %Y')} — {ArkainBrand.COMPANY}")

    # Page number
    canvas_obj.setFont(ArkainBrand.FONT_MONO, 8)
    canvas_obj.setFillColor(ArkainBrand.INDIGO)
    canvas_obj.drawRightString(width - 30, 28, f"{doc.page}")

    canvas_obj.restoreState()


def arkain_cover_page(canvas_obj, doc):
    """Draw the cover page — no header/footer, just the branded cover."""
    canvas_obj.saveState()
    width, height = letter

    # Full dark background
    canvas_obj.setFillColor(ArkainBrand.HEADER_BG)
    canvas_obj.rect(0, 0, width, height, fill=1, stroke=0)

    # Gold gradient bar at top
    canvas_obj.setFillColor(ArkainBrand.GOLD)
    canvas_obj.rect(0, height - 6, width, 6, fill=1, stroke=0)

    # Geometric accent (diagonal lines)
    canvas_obj.setStrokeColor(HexColor("#1e1e4a"))
    canvas_obj.setLineWidth(0.3)
    for i in range(0, int(width) + 200, 40):
        canvas_obj.line(i, 0, i - 200, height)

    # Company logo area
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont(ArkainBrand.FONT_HEADING, 36)
    canvas_obj.drawString(60, height - 120, "ARKAIN")
    canvas_obj.setFillColor(ArkainBrand.GOLD)
    canvas_obj.drawString(218, height - 120, "STUDIO")

    canvas_obj.setFillColor(ArkainBrand.TEXT_MUTED)
    canvas_obj.setFont(ArkainBrand.FONT_BODY, 11)
    canvas_obj.drawString(60, height - 145, "Slot Game Intelligence Engine")

    # Accent line
    canvas_obj.setStrokeColor(ArkainBrand.GOLD)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(60, height - 165, 300, height - 165)

    # Game title (from doc attributes)
    game_title = getattr(doc, '_arkain_game_title', 'Untitled Game')
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont(ArkainBrand.FONT_HEADING, 28)

    # Word wrap long titles
    words = game_title.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        if canvas_obj.stringWidth(test, ArkainBrand.FONT_HEADING, 28) > width - 120:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test
    if current_line:
        lines.append(current_line)

    y_pos = height - 260
    for line in lines:
        canvas_obj.drawString(60, y_pos, line)
        y_pos -= 38

    # Document type
    doc_type = getattr(doc, '_arkain_doc_type', 'Game Package')
    canvas_obj.setFillColor(ArkainBrand.GOLD)
    canvas_obj.setFont(ArkainBrand.FONT_HEADING, 14)
    canvas_obj.drawString(60, y_pos - 20, doc_type.upper())

    # Metadata at bottom
    canvas_obj.setFillColor(ArkainBrand.TEXT_DIM)
    canvas_obj.setFont(ArkainBrand.FONT_BODY, 9)
    canvas_obj.drawString(60, 80, f"Date: {datetime.now().strftime('%B %d, %Y')}")
    canvas_obj.drawString(60, 66, f"Version: 1.0")
    canvas_obj.drawString(60, 52, ArkainBrand.CONFIDENTIAL)

    # Bottom gold bar
    canvas_obj.setFillColor(ArkainBrand.GOLD)
    canvas_obj.rect(0, 0, width, 4, fill=1, stroke=0)

    canvas_obj.restoreState()


# ============================================================
# Style Definitions
# ============================================================

def get_arkain_styles():
    """Return Arkain-branded paragraph styles."""
    styles = {}

    styles["title"] = ParagraphStyle(
        "ArkainTitle", fontName=ArkainBrand.FONT_HEADING,
        fontSize=24, leading=30, textColor=ArkainBrand.INDIGO,
        spaceAfter=6,
    )
    styles["subtitle"] = ParagraphStyle(
        "ArkainSubtitle", fontName=ArkainBrand.FONT_BODY,
        fontSize=12, leading=16, textColor=ArkainBrand.TEXT_MUTED,
        spaceAfter=20,
    )
    styles["h1"] = ParagraphStyle(
        "ArkainH1", fontName=ArkainBrand.FONT_HEADING,
        fontSize=18, leading=24, textColor=ArkainBrand.HEADER_BG,
        spaceBefore=24, spaceAfter=10,
        borderPadding=(0, 0, 4, 0),
    )
    styles["h2"] = ParagraphStyle(
        "ArkainH2", fontName=ArkainBrand.FONT_HEADING,
        fontSize=14, leading=18, textColor=ArkainBrand.INDIGO,
        spaceBefore=16, spaceAfter=8,
    )
    styles["h3"] = ParagraphStyle(
        "ArkainH3", fontName=ArkainBrand.FONT_HEADING,
        fontSize=11, leading=15, textColor=ArkainBrand.GOLD_DARK,
        spaceBefore=12, spaceAfter=6,
    )
    styles["body"] = ParagraphStyle(
        "ArkainBody", fontName=ArkainBrand.FONT_BODY,
        fontSize=10, leading=15, textColor=ArkainBrand.TEXT_BODY,
        spaceAfter=8, alignment=TA_JUSTIFY,
    )
    styles["body_bold"] = ParagraphStyle(
        "ArkainBodyBold", fontName=ArkainBrand.FONT_HEADING,
        fontSize=10, leading=15, textColor=ArkainBrand.TEXT_DARK,
        spaceAfter=6,
    )
    styles["caption"] = ParagraphStyle(
        "ArkainCaption", fontName=ArkainBrand.FONT_BODY,
        fontSize=8, leading=11, textColor=ArkainBrand.TEXT_MUTED,
        spaceAfter=4,
    )
    styles["code"] = ParagraphStyle(
        "ArkainCode", fontName=ArkainBrand.FONT_MONO,
        fontSize=8, leading=11, textColor=ArkainBrand.TEXT_DARK,
        backColor=ArkainBrand.SECTION_BG,
        borderPadding=6, spaceAfter=8,
    )
    styles["metric_value"] = ParagraphStyle(
        "ArkainMetric", fontName=ArkainBrand.FONT_HEADING,
        fontSize=22, leading=26, textColor=ArkainBrand.INDIGO,
        alignment=TA_CENTER,
    )
    styles["metric_label"] = ParagraphStyle(
        "ArkainMetricLabel", fontName=ArkainBrand.FONT_BODY,
        fontSize=8, leading=11, textColor=ArkainBrand.TEXT_MUTED,
        alignment=TA_CENTER, spaceAfter=4,
    )

    return styles


# ============================================================
# Table Helpers
# ============================================================

def arkain_table(data, col_widths=None, header=True):
    """
    Create an Arkain-styled table.

    Args:
        data: List of lists (rows of cells)
        col_widths: Optional list of column widths
        header: If True, first row is styled as header
    """
    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), ArkainBrand.FONT_BODY),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), ArkainBrand.TEXT_BODY),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, ArkainBrand.BORDER),
    ]

    if header and len(data) > 0:
        style_commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), ArkainBrand.TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), ArkainBrand.FONT_HEADING),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
        ])

    # Alternating row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(
                ("BACKGROUND", (0, i), (-1, i), ArkainBrand.TABLE_ALT_ROW)
            )

    table = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    table.setStyle(TableStyle(style_commands))
    return table


def metric_card(value, label, color=None):
    """Create a metric display (value + label) for dashboards."""
    styles = get_arkain_styles()
    style_val = ParagraphStyle(
        "MetricVal", parent=styles["metric_value"],
        textColor=color or ArkainBrand.INDIGO,
    )
    return [
        Paragraph(str(value), style_val),
        Paragraph(label, styles["metric_label"]),
    ]


# ============================================================
# PDF Document Builder
# ============================================================

class ArkainPDFBuilder:
    """
    Builds Arkain-branded PDF documents with cover page,
    headers/footers, and consistent styling.
    """

    def __init__(
        self,
        filename: str,
        game_title: str,
        doc_type: str = "Game Package",
    ):
        self.filename = filename
        self.game_title = game_title
        self.doc_type = doc_type
        self.story = []
        self.styles = get_arkain_styles()

    def build(self):
        """Compile and save the PDF."""
        doc = SimpleDocTemplate(
            self.filename,
            pagesize=letter,
            topMargin=70,      # Space for header
            bottomMargin=60,   # Space for footer
            leftMargin=40,
            rightMargin=40,
        )

        # Attach metadata for header/footer/cover to access
        doc._arkain_title = self.doc_type
        doc._arkain_game_title = self.game_title
        doc._arkain_doc_type = self.doc_type

        # Build page templates
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id="normal",
        )

        cover_template = PageTemplate(
            id="cover",
            frames=[frame],
            onPage=arkain_cover_page,
        )
        body_template = PageTemplate(
            id="body",
            frames=[frame],
            onPage=arkain_header_footer,
        )

        doc.addPageTemplates([cover_template, body_template])

        # Insert cover page, then switch to body template
        full_story = [
            NextPageTemplate("body"),
            PageBreak(),
        ] + self.story

        doc.build(full_story)
        return self.filename

    # --- Content Methods ---

    def add_title(self, text):
        self.story.append(Paragraph(text, self.styles["title"]))

    def add_subtitle(self, text):
        self.story.append(Paragraph(text, self.styles["subtitle"]))

    def add_h1(self, text):
        self.story.append(Paragraph(text, self.styles["h1"]))
        # Gold underline
        self.story.append(HRFlowable(
            width="30%", thickness=2,
            color=ArkainBrand.GOLD, spaceAfter=12,
        ))

    def add_h2(self, text):
        self.story.append(Paragraph(text, self.styles["h2"]))

    def add_h3(self, text):
        self.story.append(Paragraph(text, self.styles["h3"]))

    def add_body(self, text):
        self.story.append(Paragraph(text, self.styles["body"]))

    def add_bold(self, text):
        self.story.append(Paragraph(text, self.styles["body_bold"]))

    def add_caption(self, text):
        self.story.append(Paragraph(text, self.styles["caption"]))

    def add_spacer(self, height=12):
        self.story.append(Spacer(1, height))

    def add_page_break(self):
        self.story.append(PageBreak())

    def add_table(self, data, col_widths=None, header=True):
        self.story.append(arkain_table(data, col_widths, header))
        self.story.append(Spacer(1, 8))

    def add_metrics_row(self, metrics):
        """
        Add a row of metric cards.
        metrics: list of (value, label, color) tuples.
        """
        data = [[]]
        for value, label, color in metrics:
            cell_content = metric_card(value, label, color)
            data[0].append(cell_content)

        col_width = 480 / len(metrics)
        table = Table(data, colWidths=[col_width] * len(metrics))
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("BACKGROUND", (0, 0), (-1, -1), ArkainBrand.SECTION_BG),
            ("BOX", (0, 0), (-1, -1), 1, ArkainBrand.BORDER),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 16))

    def add_status_box(self, text, level="info"):
        """Add a colored status/callout box."""
        color_map = {
            "info": (ArkainBrand.INDIGO, HexColor("#eef2ff")),
            "success": (ArkainBrand.SUCCESS, HexColor("#f0fdf4")),
            "warning": (ArkainBrand.WARNING, HexColor("#fefce8")),
            "danger": (ArkainBrand.DANGER, HexColor("#fef2f2")),
        }
        text_color, bg_color = color_map.get(level, color_map["info"])

        style = ParagraphStyle(
            "StatusBox", fontName=ArkainBrand.FONT_BODY,
            fontSize=9, leading=13, textColor=text_color,
            backColor=bg_color, borderPadding=10,
            borderColor=text_color, borderWidth=1,
            borderRadius=4,
        )
        self.story.append(Paragraph(text, style))
        self.story.append(Spacer(1, 8))

    def add_key_value_section(self, pairs):
        """Add a key-value pair section (for game parameters, etc.)."""
        data = [[k, str(v)] for k, v in pairs]
        col_widths = [160, 320]
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), ArkainBrand.FONT_HEADING),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), ArkainBrand.INDIGO),
            ("TEXTCOLOR", (1, 0), (1, -1), ArkainBrand.TEXT_BODY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, ArkainBrand.BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 12))

    def add_chart_image(self, image_path, width=450, caption=None):
        """Add a matplotlib chart image."""
        if os.path.exists(image_path):
            img = Image(image_path, width=width, height=width * 0.6)
            self.story.append(img)
            if caption:
                self.story.append(Paragraph(caption, self.styles["caption"]))
            self.story.append(Spacer(1, 12))


# ============================================================
# Package Generator Functions
# ============================================================

def generate_executive_summary_pdf(
    output_path: str,
    game_title: str,
    game_params: dict,
    research_summary: str,
    rtp: float,
    compliance_status: str,
):
    """Generate a 1-page executive summary PDF."""
    pdf = ArkainPDFBuilder(output_path, game_title, "Executive Summary")

    pdf.add_title(game_title)
    pdf.add_subtitle("Executive Summary — Game Concept Overview")
    pdf.add_spacer(8)

    # Key metrics row
    pdf.add_metrics_row([
        (f"{rtp}%", "Target RTP", ArkainBrand.INDIGO),
        (game_params.get("volatility", "High").upper(), "Volatility", ArkainBrand.GOLD),
        (f"{game_params.get('max_win', 5000)}x", "Max Win", ArkainBrand.SUCCESS),
        (compliance_status.upper(), "Compliance", ArkainBrand.SUCCESS if compliance_status == "green" else ArkainBrand.WARNING),
    ])

    # Parameters
    pdf.add_h2("Game Parameters")
    pdf.add_key_value_section([
        ("Theme", game_params.get("theme", "")),
        ("Grid Configuration", f"{game_params.get('grid', '5x3')}, {game_params.get('ways', '243 ways')}"),
        ("Target Markets", game_params.get("markets", "")),
        ("Art Style", game_params.get("art_style", "")),
        ("Features", ", ".join(game_params.get("features", []))),
    ])

    # Market summary
    pdf.add_h2("Market Intelligence Summary")
    pdf.add_body(research_summary)

    return pdf.build()


def generate_gdd_pdf(
    output_path: str,
    game_title: str,
    gdd_data: dict,
):
    """Generate the full Game Design Document as a branded PDF."""
    pdf = ArkainPDFBuilder(output_path, game_title, "Game Design Document")

    pdf.add_title(game_title)
    pdf.add_subtitle("Complete Game Design Document")
    pdf.add_spacer(12)

    # Executive Summary section
    pdf.add_h1("1. Executive Summary")
    pdf.add_body(gdd_data.get("executive_summary", ""))
    pdf.add_spacer(8)

    pdf.add_h2("Unique Selling Points")
    for usp in gdd_data.get("unique_selling_points", []):
        pdf.add_body(f"<b>•</b>  {usp}")

    pdf.add_page_break()

    # Game Mechanics
    pdf.add_h1("2. Grid & Mechanics")
    pdf.add_key_value_section([
        ("Grid", gdd_data.get("grid_config", "")),
        ("Payline Structure", gdd_data.get("payline_structure", "")),
        ("Volatility", gdd_data.get("target_volatility", "")),
        ("Target RTP", f"{gdd_data.get('target_rtp', 96.5)}%"),
        ("Max Win", f"{gdd_data.get('max_win_multiplier', 5000)}x"),
    ])
    pdf.add_body(gdd_data.get("base_game_description", ""))

    pdf.add_page_break()

    # Symbols
    pdf.add_h1("3. Symbol Hierarchy")
    symbols = gdd_data.get("symbols", [])
    if symbols:
        symbol_data = [["Symbol", "Tier", "3 of a Kind", "4 of a Kind", "5 of a Kind"]]
        for sym in symbols:
            pays = sym.get("pay_values", {})
            symbol_data.append([
                sym.get("name", ""),
                sym.get("tier", ""),
                f"{pays.get(3, pays.get('3', '-'))}x",
                f"{pays.get(4, pays.get('4', '-'))}x",
                f"{pays.get(5, pays.get('5', '-'))}x",
            ])
        pdf.add_table(symbol_data, col_widths=[140, 80, 80, 80, 80])

    pdf.add_page_break()

    # Features
    pdf.add_h1("4. Feature Design")
    for feat in gdd_data.get("features", []):
        pdf.add_h2(feat.get("name", "Unnamed Feature"))
        pdf.add_key_value_section([
            ("Type", feat.get("feature_type", "")),
            ("Trigger", feat.get("trigger_description", "")),
            ("RTP Contribution", f"{feat.get('expected_rtp_contribution', 'TBD')}%"),
            ("Retrigger", "Yes" if feat.get("retrigger_possible") else "No"),
        ])
        pdf.add_body(feat.get("mechanic_description", ""))
        pdf.add_spacer(8)

    pdf.add_page_break()

    # Audio Direction
    pdf.add_h1("5. Audio Direction")
    pdf.add_h3("Base Game")
    pdf.add_body(gdd_data.get("audio_base_game", ""))
    pdf.add_h3("Feature States")
    pdf.add_body(gdd_data.get("audio_features", ""))
    pdf.add_h3("Win Celebrations")
    pdf.add_body(gdd_data.get("audio_wins", ""))

    # UI/UX
    pdf.add_h1("6. UI/UX Specification")
    pdf.add_body(gdd_data.get("ui_notes", ""))

    # Differentiation
    pdf.add_h1("7. Differentiation Strategy")
    pdf.add_body(gdd_data.get("differentiation_strategy", ""))

    return pdf.build()


def generate_math_report_pdf(
    output_path: str,
    game_title: str,
    math_data: dict,
    chart_paths: Optional[dict] = None,
):
    """Generate the math model report PDF with simulation results."""
    pdf = ArkainPDFBuilder(output_path, game_title, "Math Model Report")

    pdf.add_title(game_title)
    pdf.add_subtitle("Mathematical Model & Simulation Results")
    pdf.add_spacer(12)

    sim = math_data.get("simulation", math_data.get("results", {}))

    # Key metrics
    rtp = sim.get("measured_rtp", 0)
    within_tol = sim.get("rtp_within_tolerance", False)

    pdf.add_metrics_row([
        (f"{rtp}%", "Measured RTP", ArkainBrand.SUCCESS if within_tol else ArkainBrand.DANGER),
        (f"{sim.get('hit_frequency_pct', sim.get('hit_frequency', 0))}%", "Hit Frequency", ArkainBrand.INDIGO),
        (f"{sim.get('max_win_achieved', 0):.0f}x", "Max Win Observed", ArkainBrand.GOLD),
        (f"{sim.get('volatility_index', 0):.2f}", "Volatility Index", ArkainBrand.INDIGO),
    ])

    if within_tol:
        pdf.add_status_box(f"RTP is within tolerance (±0.5% of target). Measured: {rtp}%", "success")
    else:
        pdf.add_status_box(f"WARNING: RTP deviates from target. Measured: {rtp}%. Review reel strips.", "danger")

    # RTP Breakdown
    pdf.add_h1("RTP Breakdown")
    pdf.add_key_value_section([
        ("Base Game RTP", f"{sim.get('base_game_rtp', 0)}%"),
        ("Feature RTP", f"{sim.get('feature_rtp', 0)}%"),
        ("Total Measured RTP", f"{rtp}%"),
        ("Target RTP", f"{math_data.get('target_rtp', 96.5)}%"),
        ("Deviation", f"{sim.get('rtp_deviation_from_target', rtp - math_data.get('target_rtp', 96.5)):+.4f}%"),
    ])

    # Win distribution
    pdf.add_h1("Win Distribution")
    win_dist = sim.get("win_distribution", {})
    if win_dist:
        dist_data = [["Win Bucket", "Frequency %"]]
        for bucket, pct in win_dist.items():
            dist_data.append([bucket, f"{pct:.2f}%"])
        pdf.add_table(dist_data, col_widths=[200, 200])

    # Charts
    if chart_paths:
        pdf.add_page_break()
        pdf.add_h1("Simulation Charts")
        for name, path in chart_paths.items():
            pdf.add_chart_image(path, caption=name)

    # Jurisdiction compliance
    pdf.add_h1("Jurisdiction RTP Compliance")
    compliance = sim.get("jurisdiction_compliance", math_data.get("jurisdiction_rtp_compliance", {}))
    if compliance:
        comp_data = [["Jurisdiction", "Min RTP", "Status"]]
        for j, passed in compliance.items():
            comp_data.append([j, "See config", "PASS" if passed else "FAIL"])
        pdf.add_table(comp_data, col_widths=[160, 140, 140])

    return pdf.build()


def generate_compliance_pdf(
    output_path: str,
    game_title: str,
    compliance_data: dict,
):
    """Generate the legal & compliance report PDF."""
    pdf = ArkainPDFBuilder(output_path, game_title, "Legal & Compliance Report")

    pdf.add_title(game_title)
    pdf.add_subtitle("Legal & Regulatory Compliance Review")
    pdf.add_spacer(12)

    overall = compliance_data.get("overall_status", "unknown")
    level = "success" if overall == "green" else "warning" if overall == "yellow" else "danger"
    pdf.add_status_box(f"Overall Compliance Status: {overall.upper()}", level)

    # Flags table
    pdf.add_h1("Compliance Findings")
    flags = compliance_data.get("flags", [])
    if flags:
        flag_data = [["Jurisdiction", "Category", "Risk", "Finding", "Recommendation"]]
        for flag in flags:
            flag_data.append([
                flag.get("jurisdiction", ""),
                flag.get("category", ""),
                flag.get("risk_level", ""),
                flag.get("finding", ""),
                flag.get("recommendation", ""),
            ])
        pdf.add_table(flag_data, col_widths=[70, 70, 50, 140, 140])
    else:
        pdf.add_body("No compliance flags raised. All checks passed.")

    # IP Assessment
    pdf.add_h1("Intellectual Property Assessment")
    ip = compliance_data.get("ip_assessment", {})
    pdf.add_key_value_section([
        ("Theme Clear", "Yes" if ip.get("theme_clear") else "No — Review Required"),
        ("Potential Conflicts", ", ".join(ip.get("potential_conflicts", ["None"])) or "None"),
        ("Terms to Avoid", ", ".join(ip.get("trademarked_terms_to_avoid", ["None"])) or "None"),
    ])
    pdf.add_body(ip.get("recommendation", ""))

    # Certification path
    pdf.add_h1("Certification Path")
    cert_path = compliance_data.get("certification_path", [])
    if cert_path:
        for i, step in enumerate(cert_path, 1):
            pdf.add_body(f"<b>{i}.</b>  {step}")

    return pdf.build()


def generate_full_package(
    output_dir: str,
    game_title: str,
    game_params: dict,
    research_data: Optional[dict] = None,
    gdd_data: Optional[dict] = None,
    math_data: Optional[dict] = None,
    compliance_data: Optional[dict] = None,
    chart_paths: Optional[dict] = None,
):
    """
    Generate all PDF documents for the complete game package.
    Returns a list of generated file paths.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    generated = []

    # 1. Executive Summary
    try:
        path = str(output_path / "01_Executive_Summary.pdf")
        generate_executive_summary_pdf(
            path, game_title, game_params,
            research_summary=json.dumps(research_data, indent=2, default=str)[:2000] if research_data else "Research pending.",
            rtp=game_params.get("target_rtp", 96.5),
            compliance_status=compliance_data.get("overall_status", "pending") if compliance_data else "pending",
        )
        generated.append(path)
    except Exception as e:
        print(f"Error generating executive summary: {e}")

    # 2. GDD
    if gdd_data:
        try:
            path = str(output_path / "02_Game_Design_Document.pdf")
            generate_gdd_pdf(path, game_title, gdd_data)
            generated.append(path)
        except Exception as e:
            print(f"Error generating GDD PDF: {e}")

    # 3. Math Report
    if math_data:
        try:
            path = str(output_path / "03_Math_Model_Report.pdf")
            generate_math_report_pdf(path, game_title, math_data, chart_paths)
            generated.append(path)
        except Exception as e:
            print(f"Error generating math PDF: {e}")

    # 4. Compliance
    if compliance_data:
        try:
            path = str(output_path / "04_Legal_Compliance_Report.pdf")
            generate_compliance_pdf(path, game_title, compliance_data)
            generated.append(path)
        except Exception as e:
            print(f"Error generating compliance PDF: {e}")

    return generated


# ============================================================
# CLI Entry Point (for testing)
# ============================================================

if __name__ == "__main__":
    """Generate sample PDFs for testing."""
    print("Generating sample Arkain-branded PDFs...")

    output = generate_full_package(
        output_dir="./output/sample_pdfs",
        game_title="Curse of the Pharaoh",
        game_params={
            "theme": "Ancient Egypt — Curse of the Pharaoh",
            "volatility": "high",
            "target_rtp": 96.5,
            "grid": "5x3",
            "ways": "243 ways",
            "max_win": 10000,
            "markets": "UK, Malta, Ontario",
            "art_style": "Dark, cinematic, AAA quality",
            "features": ["free_spins", "multipliers", "expanding_wilds", "cascading_reels"],
        },
        gdd_data={
            "game_title": "Curse of the Pharaoh",
            "tagline": "Unleash the curse. Reap the rewards.",
            "executive_summary": "Curse of the Pharaoh is a high-volatility 5x3 slot with 243 ways to win, featuring a unique curse mechanic where symbols transform into wilds during free spins. Targeting the premium segment of Egyptian-themed slots with AAA cinematic art direction and an escalating multiplier system that builds tension through cascading reels.",
            "target_audience": "Male 25-45, experienced slot players seeking high-volatility thrill",
            "unique_selling_points": [
                "Curse Transformation: symbols become cursed wilds during features",
                "Escalating cascade multipliers up to 15x",
                "Narrative-driven bonus round with tomb exploration",
                "10,000x max win potential",
            ],
            "grid_config": "5x3",
            "payline_structure": "243 ways to win",
            "base_game_description": "Standard left-to-right evaluation with cascading reels. Each cascade increases a multiplier by 1x. The curse meter fills with scatter hits, triggering the Curse Free Spins when full.",
            "symbols": [
                {"name": "Pharaoh's Mask", "tier": "high_pay", "pay_values": {3: 2.0, 4: 8.0, 5: 40.0}},
                {"name": "Scarab Beetle", "tier": "high_pay", "pay_values": {3: 1.5, 4: 5.0, 5: 25.0}},
                {"name": "Eye of Horus", "tier": "high_pay", "pay_values": {3: 1.0, 4: 4.0, 5: 20.0}},
                {"name": "Ankh", "tier": "high_pay", "pay_values": {3: 0.8, 4: 3.0, 5: 15.0}},
                {"name": "Canopic Jar", "tier": "high_pay", "pay_values": {3: 0.6, 4: 2.5, 5: 10.0}},
                {"name": "A", "tier": "low_pay", "pay_values": {3: 0.4, 4: 1.5, 5: 5.0}},
                {"name": "K", "tier": "low_pay", "pay_values": {3: 0.3, 4: 1.0, 5: 4.0}},
                {"name": "Q", "tier": "low_pay", "pay_values": {3: 0.25, 4: 0.8, 5: 3.0}},
                {"name": "J", "tier": "low_pay", "pay_values": {3: 0.2, 4: 0.6, 5: 2.0}},
                {"name": "Cursed Ankh Wild", "tier": "wild", "pay_values": {}},
                {"name": "Tomb Scatter", "tier": "scatter", "pay_values": {}},
            ],
            "features": [
                {
                    "name": "Curse Free Spins",
                    "feature_type": "free_spins",
                    "trigger_description": "3+ Tomb Scatter symbols anywhere",
                    "mechanic_description": "10/15/25 free spins for 3/4/5 scatters. During free spins, a random symbol is selected as the 'cursed' symbol each spin — all instances transform into wilds. The cascade multiplier carries over between spins and does not reset.",
                    "expected_rtp_contribution": 35.2,
                    "retrigger_possible": True,
                },
                {
                    "name": "Cascade Multiplier",
                    "feature_type": "multipliers",
                    "trigger_description": "Any winning combination triggers a cascade",
                    "mechanic_description": "Winning symbols are removed and new symbols fall in. Each consecutive cascade increases the multiplier by 1x (base game: up to 5x, free spins: unlimited). Multiplier resets when no new wins form.",
                    "expected_rtp_contribution": 8.5,
                    "retrigger_possible": False,
                },
            ],
            "feature_flow_description": "Base game cascades build the multiplier up to 5x. Scatter fills trigger Curse Free Spins where the multiplier has no cap and cursed symbols add wild coverage. This creates exponential win potential in extended free spin sessions.",
            "target_rtp": 96.5,
            "target_volatility": "high",
            "max_win_multiplier": 10000,
            "audio_base_game": "Ambient desert winds with subtle mystical undertones. Low-frequency percussion that intensifies during cascade sequences.",
            "audio_features": "Full orchestral score with Egyptian instrumentation — oud, ney, darbuka. Dramatic chord progressions as the curse multiplier climbs.",
            "audio_wins": "Tiered celebrations: small wins get coin sounds, big wins (20x+) get a horn fanfare, mega wins (100x+) trigger a full cinematic sequence with the pharaoh's curse breaking.",
            "ui_notes": "Mobile-first 16:9 responsive layout. Bet selector on the left, spin button centered bottom. Cascade multiplier displayed prominently above reels. Curse meter as a glowing sidebar element.",
            "differentiation_strategy": "While Book of Dead and similar titles use a simple expanding symbol mechanic, Curse of the Pharaoh combines three interlocking systems (cascades + curse transformation + escalating multiplier) that create unique win potential unavailable in competitor titles. The narrative curse mechanic adds emotional investment beyond pure math.",
        },
        math_data={
            "target_rtp": 96.5,
            "simulation": {
                "measured_rtp": 96.48,
                "rtp_within_tolerance": True,
                "hit_frequency_pct": 28.4,
                "base_game_rtp": 62.3,
                "feature_rtp": 34.18,
                "volatility_index": 8.72,
                "max_win_achieved": 8547,
                "rtp_deviation_from_target": -0.02,
                "win_distribution": {
                    "0x": 71.6, "0-1x": 12.8, "1-2x": 6.4,
                    "2-5x": 5.2, "5-20x": 2.8, "20-100x": 0.9,
                    "100-1000x": 0.28, "1000x+": 0.02,
                },
                "jurisdiction_compliance": {
                    "UK": True, "Malta": True, "Ontario": True,
                },
            },
        },
        compliance_data={
            "overall_status": "green",
            "flags": [
                {
                    "jurisdiction": "UK",
                    "category": "responsible_gambling",
                    "risk_level": "low",
                    "finding": "60-minute reality check interval required",
                    "recommendation": "Ensure reality check timer is implemented in the game client",
                },
            ],
            "ip_assessment": {
                "theme_clear": True,
                "potential_conflicts": [],
                "trademarked_terms_to_avoid": ["Book of Dead (Play'n GO trademark)"],
                "recommendation": "Egyptian mythology themes are public domain. 'Curse of the Pharaoh' title has no known trademark conflicts. Avoid using 'Book of' prefix in any marketing materials.",
            },
            "certification_path": [
                "GLI-11 (RNG certification) — primary certification",
                "UKGC approval via GLI or BMM",
                "MGA approval via iTech Labs",
                "AGCO/iGO Ontario approval via GLI",
            ],
        },
    )

    print(f"\nGenerated {len(output)} PDFs:")
    for f in output:
        print(f"  ✓ {f}")
