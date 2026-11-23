"""
keyword_match.py
-----------------
Matches skills/keywords between a resume and a job description, using the
skills taxonomy in database/skills.db plus a fallback heuristic for
technical-looking terms in the job description that aren't in the DB.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "skills.db"

# Generic words that are technically "capitalized" or list-like in a JD but
# aren't skills, so the free-text fallback extractor should ignore them.
STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "this",
    "that", "have", "has", "must", "should", "role", "team", "work", "years",
    "year", "experience", "ability", "strong", "excellent", "including",
    "etc", "job", "company", "we", "a", "an", "to", "of", "in", "on", "as",
    "is", "be", "or", "at", "by",
    # Common job-title fragments — capitalized in JDs (e.g. "Data Analyst",
    # "Senior Engineer") but not skills/keywords in their own right.
    "analyst", "engineer", "manager", "developer", "specialist",
    "coordinator", "director", "administrator", "consultant", "architect",
    "designer", "scientist", "assistant", "officer", "executive", "intern",
    "lead", "senior", "junior", "associate", "principal", "head", "vp",
}


@dataclass
class SkillHit:
    name: str
    category: str


@dataclass
class KeywordMatchResult:
    matched: list = field(default_factory=list)     # list[SkillHit] present in both
    missing: list = field(default_factory=list)      # list[SkillHit] in JD, not in resume
    extra: list = field(default_factory=list)        # list[SkillHit] in resume, not in JD
    match_percentage: float = 0.0
    jd_keyword_count: int = 0


def _load_skills(db_path: Path = DB_PATH) -> list:
    """Returns list of dicts: {name, category, aliases: [alias, ...]}."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT name, category, aliases FROM skills").fetchall()
    conn.close()
    return [
        {
            "name": r["name"],
            "category": r["category"],
            "aliases": [a.strip() for a in r["aliases"].split(",") if a.strip()],
        }
        for r in rows
    ]


def _term_pattern(term: str) -> re.Pattern:
    """Build a case-insensitive word-boundary regex for a skill term,
    handling special characters like C++, C#, .NET sensibly."""
    escaped = re.escape(term)
    # re.escape neutralizes regex special chars but we still want boundaries
    # that work even when the term itself starts/ends with punctuation.
    return re.compile(rf"(?<![\w+#.]){escaped}(?![\w+#.])", re.IGNORECASE)


def find_skills_in_text(text: str, skills: list = None) -> list:
    """Return the list of skill dicts (from the taxonomy) that appear in `text`."""
    skills = skills if skills is not None else _load_skills()
    found = []
    for skill in skills:
        terms = [skill["name"]] + skill["aliases"]
        if any(_term_pattern(t).search(text) for t in terms):
            found.append(skill)
    return found


def _extract_freeform_keywords(jd_text: str, known_names: set, known_words: set = frozenset()) -> list:
    """
    Fallback: pick up technical-looking terms in the JD that aren't in the
    skills DB (e.g. a niche in-house tool or a very new library), so the
    match isn't blind to anything outside the seed taxonomy.
    Heuristic: capitalized multi-char tokens *not* in sentence-initial
    position (to avoid flagging ordinary words like "Looking" just because
    they start a sentence), or tokens with digits/symbols typical of tech
    names (e.g. "Kubernetes", "Snowflake", "Web3").

    `known_words` holds individual words already covered by a multi-word DB
    skill (e.g. "power" and "bi" from "Power BI"), so those don't get
    re-extracted as spurious standalone keywords.
    """
    candidates = set()
    for sentence in re.split(r"[.!?\n]+", jd_text):
        words = sentence.strip().split()
        for position, raw_token in enumerate(words):
            match = re.match(r"[A-Za-z][A-Za-z0-9+#.]{1,20}", raw_token)
            if not match:
                continue
            clean = match.group(0).strip(".")
            lower = clean.lower()
            if lower in STOPWORDS or lower in known_names or lower in known_words:
                continue
            if len(clean) < 3:
                continue

            is_all_caps_short = clean.isupper() and len(clean) <= 6   # "SQL", "AWS"
            has_digit = any(ch.isdigit() for ch in clean)              # "Web3"
            # Title-case words only count if NOT the first word of a
            # sentence, since capitalization there just reflects grammar.
            is_title_case_midsentence = (
                position > 0 and clean[0].isupper() and not clean.isupper()
            )
            looks_technical = is_all_caps_short or has_digit or is_title_case_midsentence
            if looks_technical:
                candidates.add(clean)
    return sorted(candidates)


def match_keywords(resume_text: str, jd_text: str, db_path: Path = DB_PATH) -> KeywordMatchResult:
    """
    Compare a resume against a job description and return matched / missing
    / extra skills, plus an overall match percentage (matched / required).
    """
    skills = _load_skills(db_path)
    known_names = {s["name"].lower() for s in skills}
    # Individual words already "spoken for" by a multi-word skill/alias
    # (e.g. "power" + "bi" from "Power BI"), so they aren't re-extracted as
    # spurious standalone freeform keywords.
    known_words = set()
    for s in skills:
        for term in [s["name"]] + s["aliases"]:
            known_words.update(term.lower().split())

    jd_skills = find_skills_in_text(jd_text, skills)
    resume_skills = find_skills_in_text(resume_text, skills)

    jd_names = {s["name"] for s in jd_skills}
    resume_names = {s["name"] for s in resume_skills}

    # Fold in freeform technical terms found in the JD that the taxonomy missed
    freeform = _extract_freeform_keywords(jd_text, known_names, known_words)
    for term in freeform:
        jd_names.add(term)
        pattern = _term_pattern(term)
        if pattern.search(resume_text):
            resume_names.add(term)

    matched_names = jd_names & resume_names
    missing_names = jd_names - resume_names
    extra_names = resume_names - jd_names

    category_lookup = {s["name"]: s["category"] for s in skills}

    def to_hits(names):
        return sorted(
            (SkillHit(name=n, category=category_lookup.get(n, "keyword")) for n in names),
            key=lambda h: h.name.lower(),
        )

    match_pct = (len(matched_names) / len(jd_names) * 100) if jd_names else 0.0

    return KeywordMatchResult(
        matched=to_hits(matched_names),
        missing=to_hits(missing_names),
        extra=to_hits(extra_names),
        match_percentage=round(match_pct, 1),
        jd_keyword_count=len(jd_names),
    )


if __name__ == "__main__":
    sample_jd = "Looking for a Python developer with AWS, Docker, and strong SQL skills. React experience a plus."
    sample_resume = "Built APIs in Python and deployed with Docker. Familiar with PostgreSQL and Git."
    result = match_keywords(sample_resume, sample_jd)
    print(f"Match: {result.match_percentage}% ({len(result.matched)}/{result.jd_keyword_count})")
    print("Matched:", [h.name for h in result.matched])
    print("Missing:", [h.name for h in result.missing])
