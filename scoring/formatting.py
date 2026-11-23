"""
formatting.py
--------------
Checks a resume for formatting issues known to trip up ATS parsers:
tables, images, headers/footers, missing standard sections, length, and
contact-info presence. Works from the ParsedResume produced by
parser.resume_parser.
"""

from dataclasses import dataclass, field

RECOMMENDED_SECTIONS = ["experience", "education", "skills"]
MIN_WORD_COUNT = 150
MAX_WORD_COUNT = 1100   # roughly 2 pages of dense text


@dataclass
class FormattingIssue:
    severity: str   # "high" | "medium" | "low"
    message: str


@dataclass
class FormattingResult:
    score: float = 0.0                     # 0-100
    issues: list = field(default_factory=list)   # list[FormattingIssue]


def check_formatting(parsed_resume) -> FormattingResult:
    """
    `parsed_resume` is a parser.resume_parser.ParsedResume instance.
    Returns a 0-100 score and a list of specific issues, worst first.
    """
    issues = []
    deductions = 0

    # --- Structural red flags coming from the file itself ---
    if parsed_resume.has_tables:
        issues.append(FormattingIssue(
            "high",
            "Tables detected. Many ATS parsers read tables out of order or "
            "skip them entirely — avoid tables for layout or content.",
        ))
        deductions += 15

    if parsed_resume.has_images:
        issues.append(FormattingIssue(
            "medium",
            "Image(s) detected (e.g. a photo, icon, or logo). ATS parsers "
            "can't read text inside images, and photos can trigger bias "
            "screening in some hiring pipelines.",
        ))
        deductions += 10

    if getattr(parsed_resume, "layout_warnings", None):
        for warning in parsed_resume.layout_warnings:
            if "header/footer" in warning.lower():
                issues.append(FormattingIssue("high", warning))
                deductions += 15
            elif "scanned image" in warning.lower():
                issues.append(FormattingIssue("high", warning))
                deductions += 30

    # --- Contact info ---
    if not parsed_resume.email:
        issues.append(FormattingIssue(
            "high", "No email address detected — this is almost always a hard "
            "requirement for ATS candidate records.",
        ))
        deductions += 15
    if not parsed_resume.phone:
        issues.append(FormattingIssue(
            "medium", "No phone number detected.",
        ))
        deductions += 5
    if not parsed_resume.name:
        issues.append(FormattingIssue(
            "medium", "Could not confidently identify a name at the top of "
            "the resume.",
        ))
        deductions += 5

    # --- Section coverage ---
    found_sections = set(parsed_resume.sections.keys())
    for section in RECOMMENDED_SECTIONS:
        if section not in found_sections:
            issues.append(FormattingIssue(
                "high",
                f"No clearly labeled '{section.title()}' section found. Use a "
                f"standard header (e.g. \"{section.upper()}\") so ATS parsers "
                "can categorize this content correctly.",
            ))
            deductions += 10

    # --- Length ---
    wc = parsed_resume.word_count
    if wc < MIN_WORD_COUNT:
        issues.append(FormattingIssue(
            "medium",
            f"Only {wc} words detected — this resume may be too sparse to "
            "demonstrate relevant experience.",
        ))
        deductions += 10
    elif wc > MAX_WORD_COUNT:
        issues.append(FormattingIssue(
            "low",
            f"{wc} words detected — consider trimming to roughly 1-2 pages "
            "so key qualifications aren't buried.",
        ))
        deductions += 5

    if getattr(parsed_resume, "page_count", None) and parsed_resume.page_count > 3:
        issues.append(FormattingIssue(
            "low", f"{parsed_resume.page_count} pages detected — 1-2 pages is "
            "standard outside academic/research CVs.",
        ))
        deductions += 5

    # --- Bullet point usage ---
    if len(parsed_resume.bullet_points) < 3:
        issues.append(FormattingIssue(
            "low",
            "Few or no bullet points detected under experience — bulleted, "
            "scannable achievements parse and read better than dense paragraphs.",
        ))
        deductions += 5

    score = max(0.0, 100.0 - deductions)
    issues.sort(key=lambda i: {"high": 0, "medium": 1, "low": 2}[i.severity])

    return FormattingResult(score=round(score, 1), issues=issues)


if __name__ == "__main__":
    from dataclasses import dataclass as _dc

    class _Dummy:
        has_tables = True
        has_images = False
        layout_warnings = []
        email = None
        phone = "555-1234"
        name = "Jane Doe"
        sections = {"experience": "...", "skills": "..."}
        word_count = 80
        bullet_points = []
        page_count = 1

    result = check_formatting(_Dummy())
    print(f"Score: {result.score}")
    for issue in result.issues:
        print(f"[{issue.severity}] {issue.message}")
