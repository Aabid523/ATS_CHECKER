"""
suggestions.py
--------------
Aggregates keyword/formatting/grammar/rewrite analysis into one prioritized,
human-readable list of actionable suggestions — the "so what do I actually
fix" summary shown at the top of a report.
"""

from dataclasses import dataclass, field

try:
    from .grammar import check_grammar
    from .rewrite import suggest_rewrites
except ImportError:
    from grammar import check_grammar
    from rewrite import suggest_rewrites

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
MAX_MISSING_KEYWORDS_SHOWN = 8


@dataclass
class Suggestion:
    priority: str    # "high" | "medium" | "low"
    category: str    # "keywords" | "formatting" | "grammar" | "content"
    message: str


@dataclass
class SuggestionReport:
    suggestions: list = field(default_factory=list)   # list[Suggestion]
    grammar_issues: list = field(default_factory=list)
    rewrite_suggestions: list = field(default_factory=list)
    summary: str = ""


def _keyword_suggestions(keyword_result) -> list:
    if not keyword_result.missing:
        return []
    top_missing = keyword_result.missing[:MAX_MISSING_KEYWORDS_SHOWN]
    names = ", ".join(h.name for h in top_missing)
    priority = "high" if keyword_result.match_percentage < 50 else "medium"
    return [Suggestion(
        priority=priority,
        category="keywords",
        message=(
            f"Add relevant keywords the job description mentions but this "
            f"resume doesn't: {names}"
            + (f" (+{len(keyword_result.missing) - MAX_MISSING_KEYWORDS_SHOWN} more)"
               if len(keyword_result.missing) > MAX_MISSING_KEYWORDS_SHOWN else "")
            + ". Only add ones that genuinely reflect real experience."
        ),
    )]


def _formatting_suggestions(formatting_result) -> list:
    return [
        Suggestion(priority=issue.severity, category="formatting", message=issue.message)
        for issue in formatting_result.issues
    ]


def _grammar_suggestions(grammar_issues) -> list:
    return [
        Suggestion(priority=issue.severity, category="grammar", message=issue.message)
        for issue in grammar_issues
    ]


def _content_suggestions(rewrite_results) -> list:
    if not rewrite_results:
        return []
    n_flagged = len(rewrite_results)
    return [Suggestion(
        priority="medium",
        category="content",
        message=(
            f"{n_flagged} bullet point(s) could be stronger — start with an "
            "action verb and quantify impact where possible. See the "
            "bullet-by-bullet suggestions below."
        ),
    )]


def _build_summary(overall_score: float, verdict: str, n_high: int, n_total: int) -> str:
    if n_high == 0 and overall_score >= 85:
        return f"Strong resume ({overall_score}/100, {verdict}) — no high-priority issues found."
    return (
        f"{overall_score}/100 overall ({verdict}). {n_total} suggestion(s) found, "
        f"{n_high} of them high-priority — fix those first for the biggest ATS impact."
    )


def generate_suggestions(ats_result, parsed_resume, use_ai: bool = False) -> SuggestionReport:
    """
    Build the full suggestion report from an ATSScoreResult (scoring.ats_score)
    and the ParsedResume it was computed from. Set use_ai=True to also run
    the Claude-powered grammar pass and generate AI bullet rewrites
    (requires ANTHROPIC_API_KEY — silently falls back to rule-based only).
    """
    grammar_result = check_grammar(
        parsed_resume.raw_text, bullets=parsed_resume.bullet_points, use_ai=use_ai
    )
    rewrite_results = suggest_rewrites(parsed_resume.bullet_points, use_ai=use_ai)

    suggestions = []
    suggestions.extend(_keyword_suggestions(ats_result.keyword_result))
    suggestions.extend(_formatting_suggestions(ats_result.formatting_result))
    suggestions.extend(_grammar_suggestions(grammar_result.issues))
    suggestions.extend(_content_suggestions(rewrite_results))
    suggestions.sort(key=lambda s: PRIORITY_ORDER[s.priority])

    n_high = sum(1 for s in suggestions if s.priority == "high")
    summary = _build_summary(ats_result.overall_score, ats_result.verdict, n_high, len(suggestions))

    return SuggestionReport(
        suggestions=suggestions,
        grammar_issues=grammar_result.issues,
        rewrite_suggestions=rewrite_results,
        summary=summary,
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from parser.resume_parser import parse_resume_text
    from scoring.ats_score import compute_ats_score

    sample_resume_text = """Jane Doe
jane.doe@email.com

EXPERIENCE
- Responsible for managing a support team
- Built a dashboard used by 200 daily users

SKILLS
Python, SQL
"""
    parsed = parse_resume_text(sample_resume_text)
    ats_result = compute_ats_score(parsed, "Looking for a Python developer with AWS and Docker experience.")
    report = generate_suggestions(ats_result, parsed)
    print(report.summary)
    for s in report.suggestions:
        print(f"[{s.priority}] ({s.category}) {s.message}")
