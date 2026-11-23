"""
grammar.py
----------
Rule-based grammar and writing-mechanics checks for resume text, with an
optional Claude-powered pass for more nuanced feedback (see ai_client.py).
"""

import re
from dataclasses import dataclass, field

try:
    from .ai_client import call_claude
except ImportError:
    from ai_client import call_claude

# A compact list of misspellings that show up disproportionately often in
# resumes (not a general spellchecker — keeps this dependency-free).
COMMON_MISSPELLINGS = {
    "recieve": "receive", "managment": "management", "acheive": "achieve",
    "seperate": "separate", "responsibilty": "responsibility",
    "experiance": "experience", "buisness": "business",
    "enviroment": "environment", "sucessful": "successful",
    "collegue": "colleague", "definately": "definitely", "occured": "occurred",
    "thier": "their", "commited": "committed", "untill": "until",
    "publically": "publicly", "recomend": "recommend", "adress": "address",
    "beleive": "believe", "calender": "calendar", "acheived": "achieved",
    "wich": "which", "accomodate": "accommodate", "liason": "liaison",
    "priviledge": "privilege", "supercede": "supersede",
    "mangement": "management", "communicaton": "communication",
}

PASSIVE_RE = re.compile(
    r"\b(am|is|are|was|were|be|being|been)\s+(\w+ed|\w+en)\b", re.IGNORECASE
)
FIRST_PERSON_RE = re.compile(r"\b(I|I'm|I've|me|my|myself)\b")
REPEATED_WORD_RE = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)


@dataclass
class GrammarIssue:
    severity: str      # "high" | "medium" | "low"
    category: str
    message: str
    excerpt: str = ""


@dataclass
class GrammarResult:
    issues: list = field(default_factory=list)   # list[GrammarIssue]
    ai_enhanced: bool = False


def _check_misspellings(text: str) -> list:
    issues = []
    words_found = set()
    for word in re.findall(r"[A-Za-z]+", text):
        lower = word.lower()
        if lower in COMMON_MISSPELLINGS and lower not in words_found:
            words_found.add(lower)
            issues.append(GrammarIssue(
                "high", "spelling",
                f'"{word}" looks misspelled — did you mean "{COMMON_MISSPELLINGS[lower]}"?',
                excerpt=word,
            ))
    return issues


def _check_passive_voice(bullets: list) -> list:
    issues = []
    for bullet in bullets:
        match = PASSIVE_RE.search(bullet)
        if match:
            issues.append(GrammarIssue(
                "low", "passive_voice",
                "Passive voice detected — active voice reads stronger and is "
                "more common in effective resumes.",
                excerpt=bullet[:80],
            ))
    return issues


def _check_first_person(text: str) -> list:
    matches = FIRST_PERSON_RE.findall(text)
    if not matches:
        return []
    return [GrammarIssue(
        "medium", "pronoun",
        f"First-person pronouns detected ({len(matches)}x, e.g. \"{matches[0]}\") — "
        "resumes conventionally drop \"I/me/my\" and start bullets directly "
        "with an action verb.",
    )]


def _check_repeated_words(text: str) -> list:
    issues = []
    seen = set()
    for match in REPEATED_WORD_RE.finditer(text):
        pair = match.group(0).lower()
        if pair not in seen:
            seen.add(pair)
            issues.append(GrammarIssue(
                "low", "repetition",
                f'Repeated word: "{match.group(0)}".',
                excerpt=match.group(0),
            ))
    return issues


def _check_bullet_consistency(bullets: list) -> list:
    """Flag inconsistent punctuation across bullets (some end with periods,
    some don't) — a small polish issue but a common tell of a patchworked resume."""
    if len(bullets) < 3:
        return []
    ends_with_period = [b.strip().endswith(".") for b in bullets if b.strip()]
    if any(ends_with_period) and not all(ends_with_period):
        return [GrammarIssue(
            "low", "consistency",
            "Inconsistent punctuation across bullet points — some end with "
            "a period and some don't. Pick one style and use it throughout.",
        )]
    return []


def check_grammar_rule_based(text: str, bullets: list = None) -> list:
    bullets = bullets or []
    issues = []
    issues.extend(_check_misspellings(text))
    issues.extend(_check_first_person(text))
    issues.extend(_check_repeated_words(text))
    issues.extend(_check_passive_voice(bullets))
    issues.extend(_check_bullet_consistency(bullets))
    issues.sort(key=lambda i: {"high": 0, "medium": 1, "low": 2}[i.severity])
    return issues


_AI_SYSTEM_PROMPT = (
    "You are an expert resume editor. Review the resume text for grammar, "
    "tense consistency, and clarity issues only (not content/strategy). "
    "List at most 5 concrete issues, one per line, each starting with "
    "HIGH:, MEDIUM:, or LOW: for severity. Be specific and concise — no "
    "preamble, no summary, just the list."
)


def _check_grammar_ai(text: str) -> list:
    response = call_claude(
        prompt=f"Resume text:\n\n{text[:6000]}",
        system=_AI_SYSTEM_PROMPT,
        max_tokens=600,
    )
    if not response:
        return []
    issues = []
    for line in response.strip().split("\n"):
        line = line.strip("- ").strip()
        if not line:
            continue
        for sev in ("HIGH", "MEDIUM", "LOW"):
            if line.upper().startswith(sev + ":"):
                issues.append(GrammarIssue(
                    severity=sev.lower(),
                    category="ai_review",
                    message=line[len(sev) + 1:].strip(),
                ))
                break
    return issues


def check_grammar(text: str, bullets: list = None, use_ai: bool = False) -> GrammarResult:
    """
    Run grammar/mechanics checks on resume text. Rule-based checks always
    run; set use_ai=True to also run a Claude-powered pass (requires
    ANTHROPIC_API_KEY — silently skipped if not configured).
    """
    issues = check_grammar_rule_based(text, bullets)
    ai_enhanced = False

    if use_ai:
        ai_issues = _check_grammar_ai(text)
        if ai_issues:
            issues.extend(ai_issues)
            ai_enhanced = True

    return GrammarResult(issues=issues, ai_enhanced=ai_enhanced)


if __name__ == "__main__":
    sample = "I was responsible for managing a team. I recieve great feedback. The the project succeeded."
    result = check_grammar(sample, bullets=[sample])
    for issue in result.issues:
        print(f"[{issue.severity}] ({issue.category}) {issue.message}")
