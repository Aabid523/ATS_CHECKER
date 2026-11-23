"""
app.py
------
Streamlit UI for the ATS resume checker. Run with:
    streamlit run ui/app.py
"""

import sys
from pathlib import Path

# Make the ATS package root importable regardless of where streamlit is launched from
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from parser.resume_parser import parse_resume_file
from scoring.ats_score import compute_ats_score
from ai.suggestions import generate_suggestions
from ai.ai_client import is_ai_available
from reports.html_report import generate_html_report
from reports.pdf_report import generate_pdf_report

VERDICT_ICONS = {"Excellent": "🟢", "Good": "🟡", "Needs Improvement": "🟠", "Poor": "🔴"}
PRIORITY_ICONS = {"high": "🔴", "medium": "🟠", "low": "🟢"}


def main():
    st.set_page_config(page_title="ATS Resume Checker", page_icon="📄", layout="wide")
    st.title("📄 ATS Resume Checker")
    st.caption(
        "Upload a resume and paste a job description to see how it's likely "
        "to score with an automated applicant tracking system — plus concrete "
        "suggestions to improve it."
    )

    with st.sidebar:
        st.header("1. Resume")
        resume_file = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])

        st.header("2. Job Description")
        jd_text = st.text_area(
            "Paste the full job posting", height=260,
            placeholder="Paste the job description here...",
        )

        st.header("3. Options")
        ai_ready = is_ai_available()
        use_ai = st.checkbox(
            "Use AI-enhanced feedback", value=False,
            help="Uses Claude for smarter grammar checks and bullet rewrites. "
                 "Requires the ANTHROPIC_API_KEY environment variable and "
                 "`pip install anthropic`.",
        )
        if use_ai and not ai_ready:
            st.warning(
                "ANTHROPIC_API_KEY not set (or the `anthropic` package isn't "
                "installed) — continuing with rule-based analysis only."
            )

        analyze_clicked = st.button("Analyze Resume", type="primary", use_container_width=True)

    if analyze_clicked:
        _run_analysis(resume_file, jd_text, use_ai)

    if "ats_result" in st.session_state:
        _render_results(
            st.session_state["parsed"],
            st.session_state["ats_result"],
            st.session_state["suggestion_report"],
        )
    else:
        st.info("Upload a resume and paste a job description, then click **Analyze Resume**.")


def _run_analysis(resume_file, jd_text, use_ai):
    if not resume_file:
        st.error("Please upload a resume file first.")
        return
    if not jd_text or not jd_text.strip():
        st.error("Please paste a job description first.")
        return

    with st.spinner("Parsing resume..."):
        try:
            parsed = parse_resume_file(resume_file.getvalue(), filename=resume_file.name)
        except Exception as e:
            st.error(f"Couldn't parse this file: {e}")
            return

    if len(parsed.raw_text.strip()) < 20:
        st.error(
            "Almost no text could be extracted from this file. It may be a "
            "scanned image rather than real text — try a text-based PDF or "
            "DOCX export instead."
        )
        return

    with st.spinner("Scoring against the job description..."):
        ats_result = compute_ats_score(parsed, jd_text)
        suggestion_report = generate_suggestions(ats_result, parsed, use_ai=use_ai)

    st.session_state["parsed"] = parsed
    st.session_state["ats_result"] = ats_result
    st.session_state["suggestion_report"] = suggestion_report


def _render_results(parsed, ats_result, suggestion_report):
    st.divider()

    score_col, detail_col = st.columns([1, 3])
    with score_col:
        st.metric("Overall ATS Score", f"{ats_result.overall_score:.0f}/100")
    with detail_col:
        icon = VERDICT_ICONS.get(ats_result.verdict, "")
        st.subheader(f"{icon} {ats_result.verdict}")
        st.write(ats_result.verdict_detail)

    st.info(suggestion_report.summary)

    with st.expander("How is this score calculated?"):
        st.markdown(
            "- **Keyword Match (60%)** — how many of the job description's "
            "skills/keywords appear in the resume.\n"
            "- **Formatting & Structure (40%)** — ATS-unfriendly elements "
            "(tables, images, missing sections, missing contact info, "
            "unusual length) that can cause parsers to misread or drop content.\n\n"
            "This is a heuristic estimate modeled on common ATS parsing "
            "behavior, not a guarantee of how any specific employer's system "
            "will score this resume."
        )

    st.subheader("Score Breakdown")
    b1, b2 = st.columns(2)
    with b1:
        kw_raw = ats_result.breakdown["keywords_raw"]
        st.write(f"**Keyword Match** — {kw_raw:.0f}/100")
        st.progress(min(int(kw_raw), 100) / 100)
    with b2:
        fmt_raw = ats_result.breakdown["formatting_raw"]
        st.write(f"**Formatting & Structure** — {fmt_raw:.0f}/100")
        st.progress(min(int(fmt_raw), 100) / 100)

    kr = ats_result.keyword_result
    st.subheader(f"Keyword Match ({len(kr.matched)}/{kr.jd_keyword_count} found)")
    k1, k2 = st.columns(2)
    with k1:
        st.markdown("**✅ Matched**")
        st.write(", ".join(h.name for h in kr.matched) if kr.matched else "_None_")
    with k2:
        st.markdown("**❌ Missing**")
        st.write(", ".join(h.name for h in kr.missing) if kr.missing else "_None_")

    st.subheader(f"Suggestions ({len(suggestion_report.suggestions)})")
    if not suggestion_report.suggestions:
        st.success("No issues found — nice work.")
    for s in suggestion_report.suggestions:
        icon = PRIORITY_ICONS.get(s.priority, "•")
        st.markdown(f"{icon} **[{s.category.title()}]** {s.message}")

    if suggestion_report.rewrite_suggestions:
        st.subheader("Bullet Point Feedback")
        for r in suggestion_report.rewrite_suggestions:
            preview = r.original[:70] + ("..." if len(r.original) > 70 else "")
            with st.expander(f'"{preview}"'):
                for tip in r.tips:
                    st.write(f"- {tip}")
                if r.ai_rewrite:
                    st.success(f"**Suggested rewrite:** {r.ai_rewrite}")

    st.divider()
    st.subheader("Download Full Report")
    d1, d2 = st.columns(2)
    with d1:
        html_report = generate_html_report(parsed, ats_result, suggestion_report)
        st.download_button(
            "⬇ Download HTML Report", data=html_report, file_name="ats_report.html",
            mime="text/html", use_container_width=True,
        )
    with d2:
        pdf_bytes = generate_pdf_report(parsed, ats_result, suggestion_report)
        st.download_button(
            "⬇ Download PDF Report", data=pdf_bytes, file_name="ats_report.pdf",
            mime="application/pdf", use_container_width=True,
        )


if __name__ == "__main__":
    main()
