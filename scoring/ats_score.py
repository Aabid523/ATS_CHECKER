"""
ats_score.py
------------
Combines keyword_match + formatting into a single overall ATS compatibility
score (0-100) with a plain-language verdict.
"""

from dataclasses import dataclass, field

try:
    from .keyword_match import match_keywords, KeywordMatchResult
    from .formatting import check_formatting, FormattingResult
except ImportError:
    from keyword_match import match_keywords, KeywordMatchResult
    from formatting import check_formatting, FormattingResult

DEFAULT_WEIGHTS = {"keywords": 0.60, "formatting": 0.40}

VERDICT_BANDS = [
    (85, "Excellent", "Strong match — this resume is very likely to clear "
                       "automated ATS screening for this role."),
    (70, "Good", "Solid resume with a few gaps — closing them will meaningfully "
                 "raise your odds of passing ATS screening."),
    (50, "Needs Improvement", "Several notable gaps in keywords and/or "
                               "formatting that are likely hurting this resume "
                               "in ATS screening."),
    (0, "Poor", "Significant issues detected — this resume is at high risk "
                "of being filtered out before a human ever sees it."),
]


@dataclass
class ATSScoreResult:
    overall_score: float = 0.0
    verdict: str = ""
    verdict_detail: str = ""
    keyword_result: KeywordMatchResult = None
    formatting_result: FormattingResult = None
    breakdown: dict = field(default_factory=dict)   # component -> weighted contribution


def _verdict_for(score: float):
    for threshold, label, detail in VERDICT_BANDS:
        if score >= threshold:
            return label, detail
    return VERDICT_BANDS[-1][1], VERDICT_BANDS[-1][2]


def compute_ats_score(parsed_resume, jd_text: str, weights: dict = None) -> ATSScoreResult:
    """
    parsed_resume: a parser.resume_parser.ParsedResume instance.
    jd_text: the job description text to match against.
    weights: optional override for {"keywords": w1, "formatting": w2} (must sum to 1.0).
    """
    weights = weights or DEFAULT_WEIGHTS

    keyword_result = match_keywords(parsed_resume.raw_text, jd_text)
    formatting_result = check_formatting(parsed_resume)

    keyword_contribution = keyword_result.match_percentage * weights["keywords"]
    formatting_contribution = formatting_result.score * weights["formatting"]
    overall = round(keyword_contribution + formatting_contribution, 1)

    verdict, detail = _verdict_for(overall)

    return ATSScoreResult(
        overall_score=overall,
        verdict=verdict,
        verdict_detail=detail,
        keyword_result=keyword_result,
        formatting_result=formatting_result,
        breakdown={
            "keywords": round(keyword_contribution, 1),
            "formatting": round(formatting_contribution, 1),
            "keywords_raw": keyword_result.match_percentage,
            "formatting_raw": formatting_result.score,
        },
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from parser.resume_parser import parse_resume_text

    sample_resume_text = """
Jane Doe
jane.doe@email.com | (555) 123-4567

SUMMARY
Backend engineer with 5 years building scalable APIs.

EXPERIENCE
- Built and deployed microservices using Python and Docker
- Reduced API latency by 30 percent through query optimization

EDUCATION
B.S. Computer Science, State University

SKILLS
Python, Docker, PostgreSQL, Git, AWS
"""
    sample_jd = "Seeking a Python developer with Docker, AWS, and SQL experience. React is a plus."

    parsed = parse_resume_text(sample_resume_text)
    result = compute_ats_score(parsed, sample_jd)
    print(f"Overall: {result.overall_score} — {result.verdict}")
    print(result.breakdown)
