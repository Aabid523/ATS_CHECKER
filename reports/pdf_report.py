"""
pdf_report.py
--------------
Renders the same analysis as html_report.py into a downloadable PDF, using
reportlab (pure-Python, no system dependencies like wkhtmltopdf/Pango).
"""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

SEVERITY_COLORS = {
    "high": colors.HexColor("#dc2626"),
    "medium": colors.HexColor("#d97706"),
    "low": colors.HexColor("#65a30d"),
}


def _score_color(score: float):
    if score >= 85:
        return colors.HexColor("#16a34a")
    if score >= 70:
        return colors.HexColor("#65a30d")
    if score >= 50:
        return colors.HexColor("#d97706")
    return colors.HexColor("#dc2626")


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("ReportTitle", fontSize=20, leading=24, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("Meta", fontSize=9.5, textColor=colors.HexColor("#64748b")))
    styles.add(ParagraphStyle("SectionHeading", fontSize=13, leading=16,
                               fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=8,
                               textColor=colors.HexColor("#1e293b")))
    styles.add(ParagraphStyle("Body", fontSize=10, leading=14.5, textColor=colors.HexColor("#334155")))
    styles.add(ParagraphStyle("SuggestionMsg", fontSize=10, leading=14, textColor=colors.HexColor("#334155"),
                               spaceAfter=8))
    styles.add(ParagraphStyle("BulletOriginal", fontSize=10, leading=14, fontName="Helvetica-Oblique",
                               textColor=colors.HexColor("#475569"), spaceAfter=3))
    styles.add(ParagraphStyle("BulletTip", fontSize=9.5, leading=13, textColor=colors.HexColor("#334155"),
                               leftIndent=12, spaceAfter=2))
    return styles


def _tag_table(names, bg_hex, fg_hex, styles):
    """Render a wrapped list of names as small colored 'chips' inside a borderless table."""
    if not names:
        return Paragraph("None", styles["Meta"])
    chip_style = ParagraphStyle("Chip", fontSize=9, textColor=colors.HexColor(fg_hex),
                                 backColor=colors.HexColor(bg_hex), leading=12,
                                 borderPadding=(3, 6, 3, 6))
    # Simple wrapping "flow" of chips using a Table with many small cells
    chips = [Paragraph(n, chip_style) for n in names]
    rows, row, width_used, MAX_W = [], [], 0, 6.5 * inch
    for chip, name in zip(chips, names):
        est_w = 0.11 * inch * (len(name) + 4)
        if width_used + est_w > MAX_W and row:
            rows.append(row)
            row, width_used = [], 0
        row.append(chip)
        width_used += est_w
    if row:
        rows.append(row)
    flat = []
    for r in rows:
        flat.append(r)
    # Build one Table per row so cell widths can hug content
    from reportlab.platypus import Table as _T
    tables = []
    for r in rows:
        t = _T([r])
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        tables.append(t)
    return tables


def generate_pdf_report(parsed_resume, ats_result, suggestion_report) -> bytes:
    """
    Build the PDF report and return it as raw bytes (write these to a
    .pdf file, or hand them straight to a Streamlit download_button).
    """
    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.65 * inch, rightMargin=0.65 * inch,
    )
    story = []
    name = parsed_resume.name or "Candidate"
    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # --- Header ---
    story.append(Paragraph("ATS Compatibility Report", styles["ReportTitle"]))
    story.append(Paragraph(f"{name} | Generated {generated}", styles["Meta"]))
    story.append(Spacer(1, 10))

    score_color = _score_color(ats_result.overall_score)
    score_style = ParagraphStyle("Score", fontSize=34, fontName="Helvetica-Bold", textColor=score_color)
    verdict_style = ParagraphStyle("Verdict", fontSize=13, fontName="Helvetica-Bold", textColor=score_color)

    header_table = Table(
        [[Paragraph(f"{ats_result.overall_score:.0f}<font size=11>/100</font>", score_style),
          Paragraph(f"{ats_result.verdict}<br/><font size=9 color='#475569'>{ats_result.verdict_detail}</font>",
                     verdict_style)]],
        colWidths=[1.4 * inch, 5.1 * inch],
    )
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(header_table)
    story.append(Paragraph(suggestion_report.summary, styles["Body"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e2e8f0")))

    # --- Score breakdown ---
    story.append(Paragraph("Score Breakdown", styles["SectionHeading"]))
    breakdown_rows = [
        ["Keyword Match", f"{ats_result.breakdown['keywords_raw']:.0f}/100"],
        ["Formatting &amp; Structure", f"{ats_result.breakdown['formatting_raw']:.0f}/100"],
    ]
    bt = Table(
        [[Paragraph(r[0], styles["Body"]), Paragraph(r[1], styles["Body"])] for r in breakdown_rows],
        colWidths=[4.5 * inch, 2 * inch],
    )
    bt.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(bt)

    # --- Keyword match ---
    kr = ats_result.keyword_result
    story.append(Paragraph(
        f"Keyword Match ({len(kr.matched)}/{kr.jd_keyword_count} found)", styles["SectionHeading"]))
    story.append(Paragraph("<b>Matched:</b>", styles["Body"]))
    for t in _tag_table([h.name for h in kr.matched], "#dcfce7", "#166534", styles):
        story.append(t)
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Missing:</b>", styles["Body"]))
    for t in _tag_table([h.name for h in kr.missing], "#fee2e2", "#991b1b", styles):
        story.append(t)

    # --- Suggestions ---
    story.append(Paragraph(f"Suggestions ({len(suggestion_report.suggestions)})", styles["SectionHeading"]))
    if not suggestion_report.suggestions:
        story.append(Paragraph("No issues found.", styles["Body"]))
    for s in suggestion_report.suggestions:
        color_hex = SEVERITY_COLORS.get(s.priority, colors.HexColor("#64748b"))
        badge_style = ParagraphStyle("Badge", fontSize=8, fontName="Helvetica-Bold",
                                      textColor=colors.white, backColor=color_hex,
                                      borderPadding=(2, 5, 2, 5))
        story.append(Paragraph(f"{s.priority.upper()}&nbsp;&nbsp;{s.category.title()}", badge_style))
        story.append(Paragraph(s.message, styles["SuggestionMsg"]))

    # --- Bullet feedback ---
    story.append(Paragraph("Bullet Point Feedback", styles["SectionHeading"]))
    if not suggestion_report.rewrite_suggestions:
        story.append(Paragraph("No flagged bullet points.", styles["Body"]))
    for r in suggestion_report.rewrite_suggestions:
        story.append(Paragraph(f'&ldquo;{r.original}&rdquo;', styles["BulletOriginal"]))
        for tip in r.tips:
            story.append(Paragraph(f"- {tip}", styles["BulletTip"]))
        if r.ai_rewrite:
            story.append(Paragraph(f"<b>Suggested rewrite:</b> {r.ai_rewrite}", styles["BulletTip"]))
        story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()


if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from parser.resume_parser import parse_resume_text
    from scoring.ats_score import compute_ats_score
    from ai.suggestions import generate_suggestions

    text = """Jane Doe
jane.doe@email.com | (555) 123-4567

SUMMARY
Backend engineer.

EXPERIENCE
- Responsible for managing a support team
- Built a dashboard used by 200 daily users

EDUCATION
B.S. Computer Science

SKILLS
Python, SQL
"""
    parsed = parse_resume_text(text)
    ats_result = compute_ats_score(parsed, "Looking for a Python developer with AWS and Docker experience.")
    suggestion_report = generate_suggestions(ats_result, parsed)
    pdf_bytes = generate_pdf_report(parsed, ats_result, suggestion_report)
    out_path = _Path(__file__).parent / "_test_report.pdf"
    out_path.write_bytes(pdf_bytes)
    print(f"Wrote {out_path} ({len(pdf_bytes)} bytes)")
