#!/usr/bin/env python3
"""
Rival Plugin — Team Status PDF Generator

Takes raw-data.json (from team-status.py) and report.md (from team-narrative-writer agent)
and produces a polished PDF with real charts.

Dependencies: matplotlib, reportlab

Usage:
  python3 team-status-pdf.py --input .team-status/2026-04-05/raw-data.json \
      --report .team-status/2026-04-05/report.md \
      --output .team-status/2026-04-05/report.pdf
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib import rcParams
except ImportError:
    print("[rival] ERROR: matplotlib not installed. Run: pip3 install matplotlib", file=sys.stderr)
    sys.exit(1)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak,
        Table, TableStyle, KeepTogether,
    )
except ImportError:
    print("[rival] ERROR: reportlab not installed. Run: pip3 install reportlab", file=sys.stderr)
    sys.exit(1)


# Color palette (calm professional)
COLORS = {
    "primary": "#2C3E50",      # dark slate
    "accent": "#3498DB",       # blue
    "active": "#E67E22",       # orange
    "backlog": "#95A5A6",      # gray
    "completed": "#27AE60",    # green
    "pr": "#8E44AD",           # purple
    "light_bg": "#ECF0F1",     # light gray
    "text_light": "#7F8C8D",
}

# Set matplotlib style
rcParams["font.family"] = "sans-serif"
rcParams["axes.spines.top"] = False
rcParams["axes.spines.right"] = False


def log(msg: str) -> None:
    print(f"[rival] {msg}", flush=True)


# ============================================================
# Chart Generation
# ============================================================

def fig_to_image_buffer(fig, dpi=150) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def chart_workload_distribution(members: List[Dict]) -> io.BytesIO:
    """Horizontal stacked bar chart: active/backlog/completed per member."""
    sorted_members = sorted(
        members,
        key=lambda m: (
            len(m["work_items"]["active"])
            + len(m["work_items"]["backlog"])
            + len(m["work_items"]["completed"])
        ),
        reverse=True,
    )
    names = [m["member"]["name"].split()[0] + " " + m["member"]["name"].split()[-1][0] + "." for m in sorted_members]
    active = [len(m["work_items"]["active"]) for m in sorted_members]
    backlog = [len(m["work_items"]["backlog"]) for m in sorted_members]
    completed = [len(m["work_items"]["completed"]) for m in sorted_members]

    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.4)), dpi=150)
    y_pos = range(len(names))

    ax.barh(y_pos, active, color=COLORS["active"], label="Active", height=0.7)
    ax.barh(y_pos, backlog, left=active, color=COLORS["backlog"], label="Backlog", height=0.7)
    ax.barh(
        y_pos,
        completed,
        left=[a + b for a, b in zip(active, backlog)],
        color=COLORS["completed"],
        label="Completed (in window)",
        height=0.7,
    )

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Work Items", fontsize=10)
    ax.set_title("Workload Distribution by Member", fontsize=13, fontweight="bold", pad=15)
    ax.legend(loc="lower right", fontsize=9, frameon=False)
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    # Annotate totals
    for i, (a, b, c) in enumerate(zip(active, backlog, completed)):
        total = a + b + c
        ax.text(total + 0.5, i, str(total), va="center", fontsize=9, color=COLORS["text_light"])

    plt.tight_layout()
    return fig_to_image_buffer(fig)


def chart_pr_status(members: List[Dict]) -> io.BytesIO:
    """Horizontal bar: PRs per member."""
    sorted_members = sorted(members, key=lambda m: len(m["pull_requests"]), reverse=True)
    members_with_prs = [m for m in sorted_members if len(m["pull_requests"]) > 0]
    if not members_with_prs:
        # Return empty-ish
        fig, ax = plt.subplots(figsize=(6, 2), dpi=150)
        ax.text(0.5, 0.5, "No active PRs", ha="center", va="center", fontsize=12, color=COLORS["text_light"])
        ax.axis("off")
        return fig_to_image_buffer(fig)

    names = [m["member"]["name"].split()[0] for m in members_with_prs]
    counts = [len(m["pull_requests"]) for m in members_with_prs]

    fig, ax = plt.subplots(figsize=(6, max(2, len(names) * 0.4)), dpi=150)
    ax.barh(range(len(names)), counts, color=COLORS["pr"], height=0.6)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Active PRs", fontsize=10)
    ax.set_title("Active Pull Requests by Member", fontsize=13, fontweight="bold", pad=15)
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    for i, c in enumerate(counts):
        ax.text(c + 0.05, i, str(c), va="center", fontsize=9, color=COLORS["text_light"])

    plt.tight_layout()
    return fig_to_image_buffer(fig)


def chart_boards_heatmap(members: List[Dict]) -> io.BytesIO:
    """Heatmap: members vs boards (short names)."""
    # Extract short board names
    def short_board(path: str) -> str:
        parts = path.replace("\\\\", "\\").split("\\")
        # Take last 1-2 meaningful segments
        meaningful = [p for p in parts if p and p not in ("Rival Insurance Technology",)]
        if not meaningful:
            return "?"
        if len(meaningful) >= 2:
            return f"{meaningful[-2]}\\{meaningful[-1]}"[:22]
        return meaningful[-1][:22]

    # Collect unique boards
    all_boards = set()
    member_boards: Dict[str, set] = {}
    for m in members:
        name = m["member"]["name"].split()[0]
        boards_set = set()
        for board in m.get("boards", []):
            sb = short_board(board)
            all_boards.add(sb)
            boards_set.add(sb)
        member_boards[name] = boards_set

    if not all_boards:
        fig, ax = plt.subplots(figsize=(6, 2), dpi=150)
        ax.text(0.5, 0.5, "No board data", ha="center", va="center", fontsize=12, color=COLORS["text_light"])
        ax.axis("off")
        return fig_to_image_buffer(fig)

    boards_list = sorted(all_boards)
    names = list(member_boards.keys())

    # Build matrix
    matrix = []
    for name in names:
        row = [1 if b in member_boards[name] else 0 for b in boards_list]
        matrix.append(row)

    fig, ax = plt.subplots(
        figsize=(max(6, len(boards_list) * 0.6), max(3, len(names) * 0.35)),
        dpi=150,
    )
    # Custom colormap: white → blue
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("rival_heat", ["white", COLORS["accent"]])
    ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(boards_list)))
    ax.set_xticklabels(boards_list, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_title("Board Activity Heat Map", fontsize=13, fontweight="bold", pad=15)

    # Add X marks where active
    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            if val:
                ax.text(j, i, "●", ha="center", va="center", color="white", fontsize=10, fontweight="bold")

    plt.tight_layout()
    return fig_to_image_buffer(fig)


def chart_member_donut(member: Dict) -> io.BytesIO:
    """Small donut chart: one member's state breakdown."""
    active = len(member["work_items"]["active"])
    backlog = len(member["work_items"]["backlog"])
    completed = len(member["work_items"]["completed"])
    total = active + backlog + completed

    fig, ax = plt.subplots(figsize=(3, 3), dpi=150)

    if total == 0:
        ax.text(0.5, 0.5, "No items", ha="center", va="center", transform=ax.transAxes, fontsize=10, color=COLORS["text_light"])
        ax.axis("off")
        return fig_to_image_buffer(fig)

    sizes = []
    labels = []
    pie_colors = []
    if active:
        sizes.append(active)
        labels.append(f"Active ({active})")
        pie_colors.append(COLORS["active"])
    if backlog:
        sizes.append(backlog)
        labels.append(f"Backlog ({backlog})")
        pie_colors.append(COLORS["backlog"])
    if completed:
        sizes.append(completed)
        labels.append(f"Done ({completed})")
        pie_colors.append(COLORS["completed"])

    wedges, texts = ax.pie(
        sizes, colors=pie_colors, startangle=90, wedgeprops=dict(width=0.4, edgecolor="white"),
    )
    ax.text(0, 0, str(total), ha="center", va="center", fontsize=20, fontweight="bold", color=COLORS["primary"])
    ax.text(0, -0.2, "items", ha="center", va="center", fontsize=8, color=COLORS["text_light"])

    plt.tight_layout()
    return fig_to_image_buffer(fig)


# ============================================================
# Markdown Parsing
# ============================================================

def parse_report_md(md_path: Optional[Path]) -> Dict[str, str]:
    """Extract key sections from the markdown report: exec summary, per-member narratives."""
    sections = {
        "executive_summary": "",
        "members": {},  # name -> narrative
    }
    if not md_path or not md_path.exists():
        return sections

    content = md_path.read_text(encoding="utf-8")

    # Extract executive summary
    exec_match = re.search(r"## Executive Summary\s*\n\n(.+?)(?=\n---|\n## )", content, re.DOTALL)
    if exec_match:
        sections["executive_summary"] = exec_match.group(1).strip()

    # Extract per-member sections
    # Pattern: ## <Name>\n ... (stop at next ## or end)
    # We want member sections, which come after "## At-a-Glance Visualizations" or similar
    # Let's find all top-level sections that look like member names
    member_pattern = re.compile(
        r"^## ([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)+)\s*\n(.+?)(?=\n^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for match in member_pattern.finditer(content):
        name = match.group(1).strip()
        body = match.group(2).strip()
        # Skip non-member sections
        if name.lower() in ("executive summary", "at-a-glance visualizations", "repos", "summary", "notes & context", "cross-team observations", "things to note"):
            continue
        sections["members"][name] = body

    return sections


def md_to_plain(text: str, max_chars: int = 2000) -> str:
    """Convert markdown to plain text for PDF (strip markdown artifacts)."""
    # Strip headers
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Strip bold
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Strip italic
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Strip code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Strip inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text.strip()


def escape_xml(text: str) -> str:
    """Escape for ReportLab paragraph (uses XML-like tags)."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ============================================================
# PDF Assembly
# ============================================================

def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="RivalTitle",
        parent=styles["Title"],
        fontSize=28,
        textColor=colors.HexColor(COLORS["primary"]),
        spaceAfter=6,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="RivalSubtitle",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor(COLORS["text_light"]),
        spaceAfter=18,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="RivalH1",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor(COLORS["primary"]),
        spaceBefore=12,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="RivalH2",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor(COLORS["accent"]),
        spaceBefore=10,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="RivalBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2C3E50"),
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="RivalMeta",
        parent=styles["BodyText"],
        fontSize=9,
        textColor=colors.HexColor(COLORS["text_light"]),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="RivalStat",
        parent=styles["BodyText"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor(COLORS["primary"]),
    ))
    return styles


def build_cover_page(data: Dict, styles) -> List:
    story = []
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("Team Status Report", styles["RivalTitle"]))
    story.append(Paragraph(data.get("scope", "Team Brief"), styles["RivalSubtitle"]))

    # Stats box
    total_active = sum(len(m["work_items"]["active"]) for m in data["members"])
    total_backlog = sum(len(m["work_items"]["backlog"]) for m in data["members"])
    total_completed = sum(len(m["work_items"]["completed"]) for m in data["members"])
    total_prs = sum(len(m["pull_requests"]) for m in data["members"])

    stats_data = [
        ["Members", str(len(data["members"]))],
        ["Window", f"{data.get('window_days', 60)} days"],
        ["Active Items", str(total_active)],
        ["Backlog", str(total_backlog)],
        ["Completed (in window)", str(total_completed)],
        ["Active Pull Requests", str(total_prs)],
    ]
    stats_table = Table(stats_data, colWidths=[2.5 * inch, 2 * inch])
    stats_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(COLORS["text_light"])),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor(COLORS["primary"])),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#ECF0F1")),
    ]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(stats_table)
    story.append(Spacer(1, 0.5 * inch))

    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d"))
    story.append(Paragraph(f"Generated: {escape_xml(generated_at)}", styles["RivalMeta"]))
    story.append(Paragraph(f"Source: Azure DevOps — {escape_xml(data.get('organization', ''))}/{escape_xml(data.get('project', ''))}", styles["RivalMeta"]))

    story.append(PageBreak())
    return story


def build_executive_summary(sections: Dict, styles) -> List:
    story = []
    if not sections.get("executive_summary"):
        return story

    story.append(Paragraph("Executive Summary", styles["RivalH1"]))
    text = md_to_plain(sections["executive_summary"], max_chars=3000)
    # Split paragraphs
    for para in text.split("\n\n"):
        if para.strip():
            story.append(Paragraph(escape_xml(para.strip()), styles["RivalBody"]))
    story.append(Spacer(1, 0.2 * inch))
    return story


def build_charts_section(data: Dict, styles) -> List:
    story = []
    story.append(Paragraph("At-a-Glance", styles["RivalH1"]))

    # Workload chart
    log("  Generating workload chart...")
    workload_img = chart_workload_distribution(data["members"])
    story.append(Image(workload_img, width=6.5 * inch, height=None, hAlign="CENTER"))
    story.append(Spacer(1, 0.2 * inch))

    # PR status chart
    log("  Generating PR chart...")
    pr_img = chart_pr_status(data["members"])
    story.append(Image(pr_img, width=5 * inch, height=None, hAlign="CENTER"))
    story.append(Spacer(1, 0.2 * inch))

    story.append(PageBreak())

    # Board heatmap
    log("  Generating heatmap...")
    heatmap_img = chart_boards_heatmap(data["members"])
    story.append(Paragraph("Board Activity", styles["RivalH1"]))
    story.append(Image(heatmap_img, width=7 * inch, height=None, hAlign="CENTER"))

    story.append(PageBreak())
    return story


def build_member_sections(data: Dict, sections: Dict, styles) -> List:
    story = []
    story.append(Paragraph("Per-Member Detail", styles["RivalH1"]))
    story.append(Spacer(1, 0.2 * inch))

    for idx, member in enumerate(data["members"]):
        name = member["member"]["name"]
        email = member["member"]["email"]
        active = len(member["work_items"]["active"])
        backlog = len(member["work_items"]["backlog"])
        completed = len(member["work_items"]["completed"])
        prs = len(member["pull_requests"])
        commits = member["member"].get("commits_60d", 0)
        boards_count = len(member.get("boards", []))

        log(f"  Rendering section for {name}...")

        # Member header
        story.append(Paragraph(escape_xml(name), styles["RivalH2"]))
        story.append(Paragraph(
            f"{escape_xml(email)} &nbsp;•&nbsp; {active} active &nbsp;•&nbsp; {backlog} backlog &nbsp;•&nbsp; {completed} done &nbsp;•&nbsp; {prs} PRs &nbsp;•&nbsp; {commits} commits/60d &nbsp;•&nbsp; {boards_count} boards",
            styles["RivalMeta"],
        ))

        # Narrative from markdown
        if name in sections.get("members", {}):
            narrative = md_to_plain(sections["members"][name], max_chars=4000)
            for para in narrative.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(escape_xml(para.strip()), styles["RivalBody"]))

        # Ticket table (compact)
        ticket_data = [["ID", "Type", "Title", "State"]]
        for wi in member["work_items"]["active"][:15]:
            f = wi.get("fields", {})
            title = f.get("System.Title", "")[:60]
            ticket_data.append([
                f"#{wi.get('id')}",
                f.get("System.WorkItemType", "")[:12],
                title,
                f.get("System.State", "")[:10],
            ])
        if len(member["work_items"]["active"]) > 15:
            ticket_data.append(["...", "", f"... and {len(member['work_items']['active']) - 15} more active items", ""])

        if len(ticket_data) > 1:
            t = Table(ticket_data, colWidths=[0.6 * inch, 0.9 * inch, 3.8 * inch, 0.8 * inch], repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLORS["primary"])),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
                ("TOPPADDING", (0, 1), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#ECF0F1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FAFBFC")),
            ]))
            story.append(Spacer(1, 0.1 * inch))
            story.append(t)

        story.append(Spacer(1, 0.25 * inch))

        # Page break every 2 members
        if (idx + 1) % 2 == 0 and idx < len(data["members"]) - 1:
            story.append(PageBreak())

    return story


def build_pdf(
    raw_data_path: Path,
    report_md_path: Optional[Path],
    output_path: Path,
) -> None:
    log(f"Loading raw data: {raw_data_path}")
    data = json.loads(raw_data_path.read_text(encoding="utf-8"))

    log(f"Loading narrative: {report_md_path}")
    sections = parse_report_md(report_md_path)

    log(f"Building PDF: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="Rival Team Status",
    )

    styles = build_styles()
    story = []

    story.extend(build_cover_page(data, styles))
    story.extend(build_executive_summary(sections, styles))
    story.extend(build_charts_section(data, styles))
    story.extend(build_member_sections(data, sections, styles))

    doc.build(story)
    log(f"PDF written: {output_path}")


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Rival — Team Status PDF generator")
    parser.add_argument("--input", required=True, help="Path to raw-data.json")
    parser.add_argument("--report", help="Path to report.md (optional — for narrative text)")
    parser.add_argument("--output", required=True, help="Output PDF path")
    args = parser.parse_args(argv)

    raw_data_path = Path(args.input)
    if not raw_data_path.exists():
        log(f"ERROR: raw data not found: {raw_data_path}")
        return 1

    report_md_path = Path(args.report) if args.report else None

    output_path = Path(args.output)
    build_pdf(raw_data_path, report_md_path, output_path)
    print(str(output_path.resolve()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"[rival] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1)
