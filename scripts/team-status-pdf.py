#!/usr/bin/env python3
"""
Rival Plugin — Team Status PDF Generator

Produces a dense 2-page dashboard PDF from raw-data.json + report.md.
Dependencies: matplotlib, reportlab

Usage:
  python3 team-status-pdf.py --input raw-data.json --report report.md --output report.pdf
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
except ImportError:
    print("[rival] ERROR: matplotlib not installed. Run: pip3 install matplotlib", file=sys.stderr)
    sys.exit(1)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak,
        Table, TableStyle, KeepTogether, HRFlowable,
    )
except ImportError:
    print("[rival] ERROR: reportlab not installed. Run: pip3 install reportlab", file=sys.stderr)
    sys.exit(1)


# Color palette — professional, calm
COLORS = {
    "primary": "#1F2937",       # near-black
    "accent": "#2563EB",        # blue
    "active": "#F59E0B",        # amber
    "backlog": "#9CA3AF",       # gray
    "completed": "#10B981",     # emerald
    "pr": "#8B5CF6",            # violet
    "border": "#E5E7EB",
    "bg_soft": "#F9FAFB",
    "text_muted": "#6B7280",
    "text_strong": "#111827",
}

rcParams["font.family"] = "sans-serif"
rcParams["font.size"] = 9
rcParams["axes.spines.top"] = False
rcParams["axes.spines.right"] = False
rcParams["axes.edgecolor"] = "#D1D5DB"
rcParams["axes.labelcolor"] = "#374151"
rcParams["xtick.color"] = "#6B7280"
rcParams["ytick.color"] = "#374151"


def log(msg: str) -> None:
    print(f"[rival] {msg}", flush=True)


# ============================================================
# Chart Generation (sized for 2-column layout in PDF)
# ============================================================

def fig_to_buf(fig, dpi=180) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white", pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return buf


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1][0]}."
    return parts[0] if parts else full_name


def chart_workload(members: List[Dict]) -> io.BytesIO:
    """Compact horizontal stacked bars: active/backlog/completed."""
    sorted_members = sorted(
        members,
        key=lambda m: len(m["work_items"]["active"]) + len(m["work_items"]["backlog"]) + len(m["work_items"]["completed"]),
        reverse=True,
    )
    names = [_short_name(m["member"]["name"]) for m in sorted_members]
    active = [len(m["work_items"]["active"]) for m in sorted_members]
    backlog = [len(m["work_items"]["backlog"]) for m in sorted_members]
    completed = [len(m["work_items"]["completed"]) for m in sorted_members]

    fig_height = max(3.0, len(names) * 0.35)
    fig, ax = plt.subplots(figsize=(7.0, fig_height), dpi=180)
    y = range(len(names))

    ax.barh(y, active, color=COLORS["active"], label="Active", height=0.7)
    ax.barh(y, backlog, left=active, color=COLORS["backlog"], label="Backlog", height=0.7)
    ax.barh(y, completed, left=[a + b for a, b in zip(active, backlog)], color=COLORS["completed"], label="Done", height=0.7)

    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=11)
    ax.invert_yaxis()
    ax.set_xlabel("Work Items", fontsize=10, color="#374151")
    ax.set_title("Workload Distribution", fontsize=14, fontweight="bold", pad=12, color=COLORS["primary"], loc="left")
    ax.legend(loc="upper right", fontsize=10, frameon=False, ncol=3, bbox_to_anchor=(1.0, 1.04))
    ax.grid(axis="x", alpha=0.25, linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=9)

    max_total = max([a + b + c for a, b, c in zip(active, backlog, completed)] or [1])
    for i, (a, b, c) in enumerate(zip(active, backlog, completed)):
        total = a + b + c
        if total > 0:
            ax.text(total + max_total * 0.015, i, str(total),
                    va="center", fontsize=10, color=COLORS["text_muted"], fontweight="bold")

    plt.tight_layout()
    return fig_to_buf(fig)


def chart_state_donut(members: List[Dict]) -> io.BytesIO:
    """Donut chart: overall state breakdown team-wide."""
    total_active = sum(len(m["work_items"]["active"]) for m in members)
    total_backlog = sum(len(m["work_items"]["backlog"]) for m in members)
    total_done = sum(len(m["work_items"]["completed"]) for m in members)
    total = total_active + total_backlog + total_done

    fig, ax = plt.subplots(figsize=(2.8, 2.8), dpi=180)
    if total == 0:
        ax.text(0.5, 0.5, "No items", ha="center", va="center", transform=ax.transAxes, color=COLORS["text_muted"])
        ax.axis("off")
        return fig_to_buf(fig)

    sizes = [total_active, total_backlog, total_done]
    pie_colors = [COLORS["active"], COLORS["backlog"], COLORS["completed"]]
    labels = [f"Active\n{total_active}", f"Backlog\n{total_backlog}", f"Done\n{total_done}"]

    wedges, _ = ax.pie(sizes, colors=pie_colors, startangle=90,
                       wedgeprops=dict(width=0.35, edgecolor="white", linewidth=2))
    ax.text(0, 0.05, str(total), ha="center", va="center", fontsize=22, fontweight="bold", color=COLORS["primary"])
    ax.text(0, -0.18, "items", ha="center", va="center", fontsize=9, color=COLORS["text_muted"])

    # Legend
    from matplotlib.patches import Patch
    legend_patches = [
        Patch(facecolor=COLORS["active"], label=f"Active ({total_active})"),
        Patch(facecolor=COLORS["backlog"], label=f"Backlog ({total_backlog})"),
        Patch(facecolor=COLORS["completed"], label=f"Done ({total_done})"),
    ]
    ax.legend(handles=legend_patches, loc="lower center", bbox_to_anchor=(0.5, -0.2),
              fontsize=8, frameon=False, ncol=1)
    ax.set_title("Team Total", fontsize=12, fontweight="bold", pad=5, color=COLORS["primary"])

    plt.tight_layout()
    return fig_to_buf(fig)


def chart_heatmap(members: List[Dict]) -> io.BytesIO:
    """Compact board heatmap — readable labels."""
    def short_board(path: str) -> str:
        parts = path.replace("\\\\", "\\").split("\\")
        meaningful = [p for p in parts if p and "Rival Insurance Technology" not in p]
        if not meaningful:
            return "?"
        # Use the second-to-last if deep, else last
        if len(meaningful) >= 2:
            return meaningful[-1][:18] if len(meaningful[-1]) <= 18 else meaningful[-1][:15] + "..."
        return meaningful[-1][:18]

    all_boards = []
    member_boards: Dict[str, set] = {}
    for m in members:
        name = _short_name(m["member"]["name"])
        bset = set()
        for b in m.get("boards", []):
            sb = short_board(b)
            if sb not in all_boards:
                all_boards.append(sb)
            bset.add(sb)
        member_boards[name] = bset

    if not all_boards:
        fig, ax = plt.subplots(figsize=(6, 2), dpi=180)
        ax.text(0.5, 0.5, "No board data", ha="center", va="center", color=COLORS["text_muted"])
        ax.axis("off")
        return fig_to_buf(fig)

    # Sort boards by total usage desc
    board_usage = {b: sum(1 for bs in member_boards.values() if b in bs) for b in all_boards}
    boards_sorted = sorted(all_boards, key=lambda b: -board_usage[b])

    names = list(member_boards.keys())
    matrix = [[1 if b in member_boards[n] else 0 for b in boards_sorted] for n in names]

    cell_w = 0.35
    cell_h = 0.28
    fig_w = max(6, len(boards_sorted) * cell_w + 2)
    fig_h = max(2.5, len(names) * cell_h + 1.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=180)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("r", ["#F3F4F6", COLORS["accent"]])
    ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(boards_sorted)))
    ax.set_xticklabels(boards_sorted, rotation=35, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_title("Board Activity", fontsize=12, fontweight="bold", pad=10, color=COLORS["primary"], loc="left")

    # Grid lines between cells
    ax.set_xticks([x - 0.5 for x in range(len(boards_sorted) + 1)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(len(names) + 1)], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    plt.tight_layout()
    return fig_to_buf(fig)


# ============================================================
# Markdown Parsing (for executive summary only)
# ============================================================

def parse_exec_summary(md_path: Optional[Path]) -> str:
    if not md_path or not md_path.exists():
        return ""
    content = md_path.read_text(encoding="utf-8")
    m = re.search(r"## Executive Summary\s*\n\n(.+?)(?=\n---|\n## )", content, re.DOTALL)
    if not m:
        return ""
    text = m.group(1).strip()
    # Strip markdown
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def parse_per_repo_sections(md_path: Optional[Path]) -> List[Dict]:
    """Extract ### `repo-name` sections from the Per-Repo Activity portion."""
    if not md_path or not md_path.exists():
        return []
    content = md_path.read_text(encoding="utf-8")
    # Find the Per-Repo Activity block
    section_match = re.search(r"## Per-Repo Activity\s*\n(.+?)(?=\n## |\Z)", content, re.DOTALL)
    if not section_match:
        return []
    block = section_match.group(1)

    repos = []
    # Each repo subsection starts with ### `repo-name`
    repo_pattern = re.compile(r"### `([^`]+)`\s*\n(.+?)(?=\n### `|\Z)", re.DOTALL)
    for m in repo_pattern.finditer(block):
        name = m.group(1).strip()
        body = m.group(2).strip()
        repos.append({"name": name, "body": body})
    return repos


def extract_member_focus(md_path: Optional[Path]) -> Dict[str, str]:
    """Extract a 1-line focus per member from the Per-Member Summary section.

    Format: **Name** · boards · N/N/N · N PRs · N commits · repos — focus text.
    """
    focus = {}
    if not md_path or not md_path.exists():
        return focus
    content = md_path.read_text(encoding="utf-8")

    # Find the Per-Member Summary section
    section_match = re.search(r"## Per-Member Summary\s*\n(.+?)(?=\n## |\Z)", content, re.DOTALL)
    if not section_match:
        return focus
    block = section_match.group(1)

    # Match each line: **Name** ... — focus
    # The line has " — " (em-dash) separating stats from the focus text
    for line in block.split("\n"):
        line = line.strip()
        if not line.startswith("**"):
            continue
        # Extract name
        name_match = re.match(r"\*\*([^*]+)\*\*", line)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        # Extract text after em-dash (—) which separates stats from focus
        parts = line.split(" — ", 1)
        if len(parts) == 2:
            focus_text = parts[1].strip()
            # Trim to first sentence-ish (stop at bold markers or end)
            focus_text = re.sub(r"\*\*[^*]+\*\*\.?$", "", focus_text).strip().rstrip(".")
            focus[name] = focus_text[:180]
    return focus


def escape_xml(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def safe_paragraph(text: str, style) -> Paragraph:
    """Escape XML but preserve <b>, <i>, <font> tags."""
    # Protect tags
    placeholders = {
        "<b>": "\x00B_O\x00", "</b>": "\x00B_C\x00",
        "<i>": "\x00I_O\x00", "</i>": "\x00I_C\x00",
    }
    for src, dst in placeholders.items():
        text = text.replace(src, dst)
    # Protect <font ...> and </font>
    font_tags = re.findall(r'<font[^>]*>', text)
    for i, tag in enumerate(font_tags):
        text = text.replace(tag, f"\x00FONT_O_{i}\x00", 1)
    text = text.replace("</font>", "\x00FONT_C\x00")

    text = escape_xml(text)

    # Restore
    for src, dst in placeholders.items():
        text = text.replace(dst, src)
    for i, tag in enumerate(font_tags):
        text = text.replace(f"\x00FONT_O_{i}\x00", tag)
    text = text.replace("\x00FONT_C\x00", "</font>")
    return Paragraph(text, style)


# ============================================================
# PDF Layout
# ============================================================

def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DTitle", fontName="Helvetica-Bold", fontSize=20,
                              textColor=colors.HexColor(COLORS["primary"]), leading=24, spaceAfter=2))
    styles.add(ParagraphStyle(name="DSubtitle", fontName="Helvetica", fontSize=10,
                              textColor=colors.HexColor(COLORS["text_muted"]), leading=14, spaceAfter=8))
    styles.add(ParagraphStyle(name="DH2", fontName="Helvetica-Bold", fontSize=11,
                              textColor=colors.HexColor(COLORS["primary"]), leading=14,
                              spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="DBody", fontName="Helvetica", fontSize=9,
                              textColor=colors.HexColor(COLORS["text_strong"]), leading=12,
                              alignment=TA_JUSTIFY, spaceAfter=6))
    styles.add(ParagraphStyle(name="DSmall", fontName="Helvetica", fontSize=8,
                              textColor=colors.HexColor(COLORS["text_muted"]), leading=10))
    styles.add(ParagraphStyle(name="DStat", fontName="Helvetica-Bold", fontSize=18,
                              textColor=colors.HexColor(COLORS["primary"]), leading=20, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="DStatLabel", fontName="Helvetica", fontSize=7.5,
                              textColor=colors.HexColor(COLORS["text_muted"]), leading=10,
                              alignment=TA_LEFT, spaceBefore=-2))
    return styles


def build_header(data: Dict, styles) -> List:
    story = []
    scope = data.get("scope", "Team Brief")
    generated = data.get("generated_at", "")
    window = data.get("window_days", 60)

    # Title row
    story.append(Paragraph(f"Team Status — {escape_xml(scope)}", styles["DTitle"]))
    story.append(Paragraph(
        f"Last {window} days &nbsp;•&nbsp; {escape_xml(generated[:10])} &nbsp;•&nbsp; "
        f"{escape_xml(data.get('organization', ''))}/{escape_xml(data.get('project', ''))}",
        styles["DSubtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(COLORS["border"]),
                            spaceBefore=2, spaceAfter=10))
    return story


def build_stat_cards(data: Dict, styles) -> Table:
    """Horizontal stat cards."""
    total_active = sum(len(m["work_items"]["active"]) for m in data["members"])
    total_backlog = sum(len(m["work_items"]["backlog"]) for m in data["members"])
    total_done = sum(len(m["work_items"]["completed"]) for m in data["members"])
    total_prs = sum(len(m["pull_requests"]) for m in data["members"])
    member_count = len(data["members"])

    stats = [
        (str(member_count), "MEMBERS"),
        (str(total_active), "ACTIVE"),
        (str(total_backlog), "BACKLOG"),
        (str(total_done), "DONE"),
        (str(total_prs), "PRs"),
    ]

    # Build cells
    cells = []
    for val, label in stats:
        para_val = Paragraph(val, styles["DStat"])
        para_lbl = Paragraph(label, styles["DStatLabel"])
        cells.append([para_val, para_lbl])

    # Transpose so row = stats across, 2 rows (value, label)
    row_vals = [c[0] for c in cells]
    row_lbls = [c[1] for c in cells]
    t = Table([row_vals, row_lbls], colWidths=[1.3 * inch] * 5, rowHeights=[0.28 * inch, 0.2 * inch])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(COLORS["bg_soft"])),
        ("LINEAFTER", (0, 0), (3, -1), 0.5, colors.HexColor(COLORS["border"])),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def build_exec_summary(exec_text: str, styles) -> List:
    story = []
    if not exec_text:
        return story
    story.append(Paragraph("Executive Summary", styles["DH2"]))
    for para in exec_text.split("\n\n"):
        para = para.strip()
        if para:
            story.append(safe_paragraph(para, styles["DBody"]))
    return story


def build_charts_grid(data: Dict, styles) -> List:
    """Two-column layout: workload chart on left, donut on right."""
    from reportlab.lib.utils import ImageReader
    story = []
    log("  Generating workload chart...")
    workload_buf = chart_workload(data["members"])
    iw, ih = ImageReader(workload_buf).getSize()
    scale = min((5.0 * inch) / iw, (4.2 * inch) / ih)
    workload_buf.seek(0)
    workload_img = Image(workload_buf, width=iw * scale, height=ih * scale)

    log("  Generating donut chart...")
    donut_buf = chart_state_donut(data["members"])
    iw, ih = ImageReader(donut_buf).getSize()
    scale = min((2.3 * inch) / iw, (2.6 * inch) / ih)
    donut_buf.seek(0)
    donut_img = Image(donut_buf, width=iw * scale, height=ih * scale)

    grid = Table([[workload_img, donut_img]], colWidths=[5.1 * inch, 2.4 * inch])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(grid)
    story.append(Spacer(1, 0.15 * inch))
    return story


def build_heatmap(data: Dict, styles) -> List:
    story = []
    log("  Generating heatmap...")
    # Generate and constrain to fit
    heatmap_buf = chart_heatmap(data["members"])
    # Read actual dimensions
    from reportlab.lib.utils import ImageReader
    img_reader = ImageReader(heatmap_buf)
    iw, ih = img_reader.getSize()
    max_w = 7.3 * inch
    max_h = 3.2 * inch
    scale = min(max_w / iw, max_h / ih)
    heatmap_buf.seek(0)
    heatmap_img = Image(heatmap_buf, width=iw * scale, height=ih * scale)
    story.append(heatmap_img)
    story.append(Spacer(1, 0.1 * inch))
    return story


def build_per_repo_section(md_path: Optional[Path], styles) -> List:
    """Render per-repo activity as compact cards."""
    repos = parse_per_repo_sections(md_path)
    story = []
    if not repos:
        return story

    story.append(Paragraph("Per-Repo Activity", styles["DH2"]))

    for repo in repos:
        name = repo["name"]
        body = repo["body"]

        # Extract structured fields from body
        what_does = ""
        activity = ""
        contributors = ""
        current_work = []
        active_prs = []
        insight = ""

        # Parse "What it does:" line
        m = re.search(r"\*\*What it does:\*\*\s*(.+?)(?:\n|$)", body)
        if m:
            what_does = m.group(1).strip()

        # Activity
        m = re.search(r"\*\*Activity[^:]*:\*\*\s*(.+?)(?:\n|$)", body)
        if m:
            activity = m.group(1).strip()

        # Contributors
        m = re.search(r"\*\*Contributors:\*\*\s*(.+?)(?:\n|$)", body)
        if m:
            contributors = m.group(1).strip()

        # Current work bullets
        cw_match = re.search(r"\*\*Current work[^:]*:\*\*\s*(.+?)(?=\n\*\*|\Z)", body, re.DOTALL)
        if cw_match:
            cw_text = cw_match.group(1).strip()
            for line in cw_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    current_work.append(line[2:].strip())
                elif line and not line.startswith("*"):
                    # Single-line summary
                    if not current_work:
                        current_work.append(line)

        # Active PRs bullets
        pr_match = re.search(r"\*\*Active PRs:\*\*\s*(.+?)(?=\n\*\*|\Z)", body, re.DOTALL)
        if pr_match:
            pr_text = pr_match.group(1).strip()
            for line in pr_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    active_prs.append(line[2:].strip())
                elif line.lower() == "none.":
                    active_prs.append("None")

        # Insight
        m = re.search(r"\*\*What this tells us:\*\*\s*(.+?)(?=\n\*\*|\n---|\Z)", body, re.DOTALL)
        if m:
            insight = m.group(1).strip().replace("\n", " ")

        # Build card
        card_story = []
        # Repo name header
        card_story.append(Paragraph(
            f'<font name="Courier-Bold" size="10" color="{COLORS["accent"]}">{escape_xml(name)}</font>',
            styles["DBody"],
        ))

        # Meta line
        if what_does:
            card_story.append(safe_paragraph(f"<b>Purpose:</b> {what_does}", styles["DSmall"]))
        if activity:
            card_story.append(safe_paragraph(f"<b>Activity:</b> {activity}", styles["DSmall"]))
        if contributors:
            card_story.append(safe_paragraph(f"<b>Contributors:</b> {contributors}", styles["DSmall"]))

        # Current work
        if current_work:
            card_story.append(Spacer(1, 0.04 * inch))
            card_story.append(Paragraph("<b>Current work:</b>", styles["DSmall"]))
            for item in current_work[:6]:
                card_story.append(safe_paragraph(f"• {item}", styles["DSmall"]))

        # Active PRs
        if active_prs and active_prs != ["None"]:
            card_story.append(Spacer(1, 0.04 * inch))
            card_story.append(Paragraph("<b>Active PRs:</b>", styles["DSmall"]))
            for pr in active_prs[:4]:
                card_story.append(safe_paragraph(f"• {pr}", styles["DSmall"]))
        elif active_prs == ["None"]:
            card_story.append(safe_paragraph("<b>Active PRs:</b> none", styles["DSmall"]))

        # Insight callout
        if insight:
            card_story.append(Spacer(1, 0.04 * inch))
            card_story.append(safe_paragraph(
                f'<font color="{COLORS["text_strong"]}"><b>Insight:</b></font> <i>{insight}</i>',
                styles["DSmall"],
            ))

        # Wrap as a bordered table
        card_table = Table([[card_story]], colWidths=[7.4 * inch])
        card_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(COLORS["border"])),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(card_table)
        story.append(Spacer(1, 0.08 * inch))

    return story


def build_member_table(data: Dict, exec_md_path: Optional[Path], styles) -> List:
    story = []
    story.append(Paragraph("Per-Member Summary", styles["DH2"]))

    focus_map = extract_member_focus(exec_md_path)

    # Sort by total work
    sorted_members = sorted(
        data["members"],
        key=lambda m: len(m["work_items"]["active"]) + len(m["work_items"]["backlog"]) + len(m["work_items"]["completed"]),
        reverse=True,
    )

    header = ["Member", "A", "B", "Done", "PR", "Commits", "Focus"]
    rows = [header]
    for m in sorted_members:
        name = m["member"]["name"]
        active = len(m["work_items"]["active"])
        backlog = len(m["work_items"]["backlog"])
        done = len(m["work_items"]["completed"])
        prs = len(m["pull_requests"])
        commits = m["member"].get("commits_60d", 0) or 0
        focus = focus_map.get(name, "")[:95]
        if focus:
            # Wrap focus in Paragraph for text wrapping
            focus_p = Paragraph(escape_xml(focus), styles["DSmall"])
        else:
            focus_p = Paragraph("—", styles["DSmall"])

        rows.append([
            Paragraph(f"<b>{escape_xml(name)}</b>", styles["DSmall"]),
            str(active),
            str(backlog),
            str(done),
            str(prs),
            str(commits),
            focus_p,
        ])

    col_widths = [1.25 * inch, 0.3 * inch, 0.3 * inch, 0.4 * inch, 0.3 * inch, 0.55 * inch, 4.4 * inch]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLORS["primary"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (1, 0), (5, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (6, 0), (6, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Body
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(COLORS["border"])),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(COLORS["bg_soft"])]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "<i>A=Active, B=Backlog, Done=Completed in window, PR=Active pull requests, Commits=last 60d</i>",
        styles["DSmall"],
    ))
    return story


def build_footer_note(styles) -> List:
    story = []
    story.append(Spacer(1, 0.15 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(COLORS["border"]),
                            spaceBefore=4, spaceAfter=4))
    story.append(Paragraph(
        "<i>Generated by Rival. Full narrative report available in report.md.</i>",
        styles["DSmall"],
    ))
    return story


def build_pdf(raw_data_path: Path, report_md_path: Optional[Path], output_path: Path) -> None:
    log(f"Loading raw data: {raw_data_path}")
    data = json.loads(raw_data_path.read_text(encoding="utf-8"))

    exec_text = parse_exec_summary(report_md_path)

    log(f"Building PDF: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.4 * inch,
        title="Team Status Report",
    )

    styles = build_styles()
    story = []

    # Page 1: Header + stats + exec summary + charts
    story.extend(build_header(data, styles))
    story.append(build_stat_cards(data, styles))
    story.append(Spacer(1, 0.18 * inch))
    story.extend(build_exec_summary(exec_text, styles))
    story.append(Spacer(1, 0.05 * inch))
    story.extend(build_charts_grid(data, styles))

    # Page 2+: Per-repo activity (THE VALUE-ADD)
    story.append(PageBreak())
    story.extend(build_header(data, styles))
    story.extend(build_per_repo_section(report_md_path, styles))

    # Final page: Member reference table
    story.append(PageBreak())
    story.extend(build_header(data, styles))
    story.extend(build_member_table(data, report_md_path, styles))
    story.extend(build_footer_note(styles))

    doc.build(story)
    log(f"PDF written: {output_path}")


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Rival — Team Status PDF generator")
    parser.add_argument("--input", required=True, help="Path to raw-data.json")
    parser.add_argument("--report", help="Path to report.md (for narrative)")
    parser.add_argument("--output", required=True, help="Output PDF path")
    args = parser.parse_args(argv)

    raw_data_path = Path(args.input)
    if not raw_data_path.exists():
        log(f"ERROR: raw data not found: {raw_data_path}")
        return 1

    report_md_path = Path(args.report) if args.report else None
    build_pdf(raw_data_path, report_md_path, Path(args.output))
    print(str(Path(args.output).resolve()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(f"[rival] ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
