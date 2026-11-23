"""
rewrite.py
----------
Analyzes resume bullet points for weak phrasing and missing quantifiable
impact, and suggests improvements. Rule-based tips always work; when
ANTHROPIC_API_KEY is configured, also generates a concrete AI rewrite.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .ai_client import call_claude
except ImportError:
    from ai_client import call_claude

DB_PATH = Path(__file__).parent.parent / "database" / "skills.db"

METRIC_RE = re.compile(
    r"(\$\s?\d|\d+\s?%|\d+x\b|\bpercent\b|\d{2,}|\bmillion\b|\bthousand\b)",
    re.IGNORECASE,
)


@dataclass
class RewriteSuggestion:
    original: str
    issues: list = field(default_factory=list)      # list[str]
    tips: list = field(default_factory=list)         # list[str], generic actionable advice
    ai_rewrite: str = ""                              # populated only if AI available


def _load_verbs(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT verb, strength FROM action_verbs").fetchall()
    conn.close()
    weak = [v for v, s in rows if s == "weak"]
    strong = [v for v, s in rows if s == "strong"]
    return weak, strong


def _starts_with_weak_phrase(bullet: str, weak_phrases: list) -> str:
    lower = bullet.strip().lower()
    for phrase in weak_phrases:
        if lower.startswith(phrase):
            return phrase
    return ""


def analyze_bullet(bullet: str, weak_phrases: list = None, strong_verbs: list = None) -> RewriteSuggestion:
    """Analyze a single bullet point and return rule-based issues + tips."""
    if weak_phrases is None or strong_verbs is None:
        weak_phrases, strong_verbs = _load_verbs()

    issues, tips = [], []

    weak_hit = _starts_with_weak_phrase(bullet, weak_phrases)
    if weak_hit:
        issues.append(f'Starts with a weak phrase ("{weak_hit}")')
        sample_verbs = ", ".join(sorted(strong_verbs)[:6])
        tips.append(
            f'Start with a strong action verb instead (e.g. {sample_verbs}) '
            f'rather than "{weak_hit}".'
        )

    if not METRIC_RE.search(bullet):
        issues.append("No quantifiable impact")
        tips.append(
            "Add a number to show scale or impact — a percentage, dollar "
            "amount, time saved, team size, or count (e.g. \"reduced load "
            "time by 40%\" instead of \"improved load time\")."
        )

    word_count = len(bullet.split())
    if word_count > 30:
        issues.append("Bullet is long")
        tips.append(
            f"This bullet is {word_count} words — tighten it to one clear "
            "achievement rather than several ideas stacked together."
        )

    return RewriteSuggestion(original=bullet, issues=issues, tips=tips)


_AI_SYSTEM_PROMPT = (
    "You are an expert resume writer. Rewrite the given resume bullet point "
    "to start with a strong action verb and include quantifiable impact "
    "where plausible, without inventing false facts or numbers that aren't "
    "implied by the original. Keep it to one line. Reply with ONLY the "
    "rewritten bullet point, no preamble, no quotes, no explanation."
)


def _ai_rewrite(bullet: str) -> str:
    response = call_claude(prompt=bullet, system=_AI_SYSTEM_PROMPT, max_tokens=150)
    return (response or "").strip().strip('"')


def suggest_rewrites(bullets: list, use_ai: bool = False, only_flagged: bool = True) -> list:
    """
    Analyze a list of bullet points. Returns a RewriteSuggestion per bullet
    (only for bullets with issues, unless only_flagged=False).
    Set use_ai=True to also populate `ai_rewrite` via Claude (requires
    ANTHROPIC_API_KEY — silently skipped otherwise).
    """
    weak_phrases, strong_verbs = _load_verbs()
    results = []

    for bullet in bullets:
        suggestion = analyze_bullet(bullet, weak_phrases, strong_verbs)
        if suggestion.issues or not only_flagged:
            if use_ai:
                suggestion.ai_rewrite = _ai_rewrite(bullet)
            results.append(suggestion)

    return results


if __name__ == "__main__":
    sample_bullets = [
        "Responsible for managing the customer support team",
        "Built and shipped a recommendation engine that increased conversion by 18%",
        "Helped with various marketing tasks",
    ]
    for s in suggest_rewrites(sample_bullets):
        print(f"- {s.original}")
        for issue in s.issues:
            print(f"    issue: {issue}")
        for tip in s.tips:
            print(f"    tip: {tip}")
