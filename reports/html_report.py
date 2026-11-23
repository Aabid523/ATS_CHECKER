"""
html_report.py
---------------
Renders a self-contained HTML report (inline CSS, no external assets) from
the parsed resume + ATS score + suggestions.
"""

import html
from datetime import datetime

SEVERITY_COLORS = {"high": "#dc2626", "medium": "#d97706", "low": "#65a30d"}
CATEGORY_LABELS = {
    "keywords": "Keywords", "formatting": "Formatting", "grammar": "Grammar",
    "content": "Content", "spelling": "Spelling", "pronoun": "Wording",
    "repetition": "Wording", "passive_voice": "Wording", "consistency": "Formatting",
    "ai_review": "AI Review",
}


def _esc(text) -> str:
    return html.escape(str(text)) if text else ""


def _score_color(score: float) -> str:
    if score >= 85:
        return "#16a34a"
    if score >= 70:
        return "#65a30d"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def _render_bar(label: str, score: float) -> str:
    color = _score_color(score)
    return f"""
    <div class="bar-row">
      <div class="bar-label">{_esc(label)}<span class="bar-score">{score:.0f}/100</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{max(score,2):.0f}%;background:{color}"></div></div>
    </div>"""


def _render_skill_tags(hits, css_class: str) -> str:
    if not hits:
        return '<p class="empty-note">None</p>'
    return "".join(f'<span class="tag {css_class}">{_esc(h.name)}</span>' for h in hits)


def _render_suggestions(suggestions) -> str:
    if not suggestions:
        return '<p class="empty-note">No issues found — nice work.</p>'
    rows = []
    for s in suggestions:
        color = SEVERITY_COLORS.get(s.priority, "#64748b")
        label = CATEGORY_LABELS.get(s.category, s.category.title())
        rows.append(f"""
        <div class="suggestion">
          <span class="badge" style="background:{color}">{s.priority.upper()}</span>
          <span class="suggestion-cat">{_esc(label)}</span>
          <p>{_esc(s.message)}</p>
        </div>""")
    return "".join(rows)


def _render_bullet_rewrites(rewrite_suggestions) -> str:
    if not rewrite_suggestions:
        return '<p class="empty-note">No flagged bullet points.</p>'
    blocks = []
    for r in rewrite_suggestions:
        tips_html = "".join(f"<li>{_esc(t)}</li>" for t in r.tips)
        ai_html = (
            f'<div class="ai-rewrite"><strong>Suggested rewrite:</strong> {_esc(r.ai_rewrite)}</div>'
            if r.ai_rewrite else ""
        )
        blocks.append(f"""
        <div class="bullet-block">
          <p class="bullet-original">"{_esc(r.original)}"</p>
          <ul>{tips_html}</ul>
          {ai_html}
        </div>""")
    return "".join(blocks)


def generate_html_report(parsed_resume, ats_result, suggestion_report, jd_source: str = "") -> str:
    """
    Build a full, self-contained HTML report string.
    parsed_resume: parser.resume_parser.ParsedResume
    ats_result: scoring.ats_score.ATSScoreResult
    suggestion_report: ai.suggestions.SuggestionReport
    """
    name = parsed_resume.name or "Candidate"
    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    overall = ats_result.overall_score
    overall_color = _score_color(overall)

    matched_tags = _render_skill_tags(ats_result.keyword_result.matched, "tag-matched")
    missing_tags = _render_skill_tags(ats_result.keyword_result.missing, "tag-missing")
    suggestions_html = _render_suggestions(suggestion_report.suggestions)
    bullets_html = _render_bullet_rewrites(suggestion_report.rewrite_suggestions)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ATS Report — {_esc(name)}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #f8fafc; color: #1e293b; margin: 0; padding: 40px 20px; line-height: 1.5;
  }}
  .container {{ max-width: 840px; margin: 0 auto; }}
  .card {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 28px 32px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 0 0 16px; color: #334155; }}
  .meta {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .score-hero {{ display: flex; align-items: center; gap: 28px; }}
  .score-circle {{
    width: 110px; height: 110px; border-radius: 50%; display: flex; flex-direction: column;
    align-items: center; justify-content: center; border: 8px solid {overall_color}; flex-shrink: 0;
  }}
  .score-circle .num {{ font-size: 30px; font-weight: 700; color: {overall_color}; }}
  .score-circle .of {{ font-size: 11px; color: #94a3b8; }}
  .verdict {{ font-size: 19px; font-weight: 700; color: {overall_color}; margin-bottom: 4px; }}
  .verdict-detail {{ color: #475569; font-size: 14px; }}
  .summary-line {{ font-size: 14px; color: #334155; margin-top: 10px; }}
  .bar-row {{ margin-bottom: 14px; }}
  .bar-label {{ display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; margin-bottom: 5px; }}
  .bar-score {{ font-weight: 400; color: #64748b; }}
  .bar-track {{ background: #e2e8f0; border-radius: 6px; height: 8px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 6px; }}
  .tag {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12.5px; margin: 3px 4px 3px 0; }}
  .tag-matched {{ background: #dcfce7; color: #166534; }}
  .tag-missing {{ background: #fee2e2; color: #991b1b; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .col-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; color: #64748b; margin-bottom: 10px; }}
  .suggestion {{ padding: 12px 0; border-bottom: 1px solid #f1f5f9; }}
  .suggestion:last-child {{ border-bottom: none; }}
  .suggestion p {{ margin: 6px 0 0; font-size: 14px; color: #334155; }}
  .badge {{ display: inline-block; color: #fff; font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 4px; letter-spacing: .03em; }}
  .suggestion-cat {{ font-size: 12px; color: #64748b; margin-left: 8px; font-weight: 600; }}
  .bullet-block {{ padding: 14px 0; border-bottom: 1px solid #f1f5f9; }}
  .bullet-block:last-child {{ border-bottom: none; }}
  .bullet-original {{ font-style: italic; color: #475569; margin: 0 0 8px; font-size: 14px; }}
  .bullet-block ul {{ margin: 0 0 8px; padding-left: 20px; font-size: 13.5px; color: #334155; }}
  .ai-rewrite {{ background: #eff6ff; border-radius: 8px; padding: 10px 14px; font-size: 13.5px; color: #1e3a8a; }}
  .empty-note {{ color: #94a3b8; font-size: 14px; font-style: italic; }}
  footer {{ text-align: center; color: #94a3b8; font-size: 12px; margin-top: 20px; }}
  @media print {{ body {{ background: #fff; padding: 0; }} .card {{ box-shadow: none; border: none; page-break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="container">

  <div class="card">
    <h1>ATS Compatibility Report</h1>
    <div class="meta">{_esc(name)} • Generated {generated}</div>
    <div class="score-hero">
      <div class="score-circle"><span class="num">{overall:.0f}</span><span class="of">/ 100</span></div>
      <div>
        <div class="verdict">{_esc(ats_result.verdict)}</div>
        <div class="verdict-detail">{_esc(ats_result.verdict_detail)}</div>
      </div>
    </div>
    <div class="summary-line">{_esc(suggestion_report.summary)}</div>
  </div>

  <div class="card">
    <h2>Score Breakdown</h2>
    {_render_bar("Keyword Match", ats_result.breakdown['keywords_raw'])}
    {_render_bar("Formatting &amp; Structure", ats_result.breakdown['formatting_raw'])}
  </div>

  <div class="card">
    <h2>Keyword Match ({len(ats_result.keyword_result.matched)}/{ats_result.keyword_result.jd_keyword_count} found)</h2>
    <div class="two-col">
      <div>
        <div class="col-title">Matched</div>
        {matched_tags}
      </div>
      <div>
        <div class="col-title">Missing</div>
        {missing_tags}
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Suggestions ({len(suggestion_report.suggestions)})</h2>
    {suggestions_html}
  </div>

  <div class="card">
    <h2>Bullet Point Feedback</h2>
    {bullets_html}
  </div>

  <footer>Generated by the ATS resume checker. Scores are heuristic estimates, not a guarantee of any specific employer's ATS behavior.</footer>
</div>
</body>
</html>"""


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
    html_out = generate_html_report(parsed, ats_result, suggestion_report)
    out_path = _Path(__file__).parent / "_test_report.html"
    out_path.write_text(html_out)
    print(f"Wrote {out_path} ({len(html_out)} chars)")
