"""
resume_parser.py
-----------------
Orchestrates pdf_parser / docx_parser and turns raw resume text into a
structured ParsedResume: contact info, detected sections, and bullet points.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

try:
    from .pdf_parser import extract_text_from_pdf
    from .docx_parser import extract_text_from_docx
except ImportError:  # allows running this file directly, outside the package
    from pdf_parser import extract_text_from_pdf
    from docx_parser import extract_text_from_docx


# Canonical section name -> header phrases that map to it (checked case-insensitively)
SECTION_HEADERS = {
    "summary": ["summary", "professional summary", "profile", "objective", "about me"],
    "experience": ["experience", "work experience", "professional experience",
                   "employment history", "work history"],
    "education": ["education", "academic background", "academic history"],
    "skills": ["skills", "technical skills", "core competencies", "key skills",
               "competencies"],
    "certifications": ["certifications", "certificates", "licenses"],
    "projects": ["projects", "personal projects", "key projects"],
    "awards": ["awards", "honors", "achievements"],
    "languages": ["languages"],
    "publications": ["publications"],
    "volunteer": ["volunteer experience", "volunteering", "community involvement"],
    "references": ["references"],
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(
    r"(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4})"
)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+/?", re.I)
BULLET_RE = re.compile(r"^\s*[•▪◦●○‣∙·\-\*]\s+")


@dataclass
class ParsedResume:
    raw_text: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    sections: dict = field(default_factory=dict)     # canonical name -> text
    bullet_points: list = field(default_factory=list)
    word_count: int = 0
    file_type: str = ""
    layout_warnings: list = field(default_factory=list)
    # layout signals passed through from the underlying pdf/docx parser
    has_images: bool = False
    has_tables: bool = False
    page_count: Optional[int] = None


def _detect_section_headers(lines: list) -> list:
    """Return [(line_index, canonical_section_name), ...] for lines that look
    like section headers (short line, matches a known header phrase)."""
    hits = []
    for i, line in enumerate(lines):
        stripped = line.strip().strip(":").strip()
        if not stripped or len(stripped) > 40:
            continue
        lower = stripped.lower()
        for canonical, phrases in SECTION_HEADERS.items():
            if lower in phrases:
                hits.append((i, canonical))
                break
    return hits


def _split_into_sections(text: str) -> dict:
    lines = text.split("\n")
    headers = _detect_section_headers(lines)
    if not headers:
        return {}

    sections = {}
    for idx, (line_no, name) in enumerate(headers):
        start = line_no + 1
        end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        # If a section name repeats (e.g. two "Projects" headers), merge them
        sections[name] = (sections.get(name, "") + "\n" + body).strip()
    return sections


def _extract_bullet_points(text: str) -> list:
    return [
        BULLET_RE.sub("", line).strip()
        for line in text.split("\n")
        if BULLET_RE.match(line) and len(line.strip()) > 3
    ]


def _guess_name(lines: list, email: Optional[str]) -> Optional[str]:
    """Heuristic: the name is almost always one of the first few non-empty
    lines, and it won't contain @, digits, or common header words."""
    skip_words = {"resume", "cv", "curriculum vitae"}
    for line in lines[:6]:
        candidate = line.strip()
        if not candidate:
            continue
        if "@" in candidate or any(c.isdigit() for c in candidate):
            continue
        if candidate.lower() in skip_words:
            continue
        if len(candidate.split()) > 5 or len(candidate) > 60:
            continue
        return candidate
    return None


def parse_resume_text(raw_text: str) -> ParsedResume:
    """Build a ParsedResume purely from already-extracted text (useful for
    testing, or for text pasted directly rather than uploaded as a file)."""
    lines = [l for l in raw_text.split("\n") if l.strip()]

    email_match = EMAIL_RE.search(raw_text)
    phone_match = PHONE_RE.search(raw_text)
    linkedin_match = LINKEDIN_RE.search(raw_text)
    github_match = GITHUB_RE.search(raw_text)

    email = email_match.group(0) if email_match else None
    sections = _split_into_sections(raw_text)
    experience_text = sections.get("experience", "")
    bullets = _extract_bullet_points(experience_text) or _extract_bullet_points(raw_text)

    return ParsedResume(
        raw_text=raw_text,
        name=_guess_name(lines, email),
        email=email,
        phone=phone_match.group(0).strip() if phone_match else None,
        linkedin=linkedin_match.group(0) if linkedin_match else None,
        github=github_match.group(0) if github_match else None,
        sections=sections,
        bullet_points=bullets,
        word_count=len(raw_text.split()),
    )


def parse_resume_file(source: Union[str, Path, bytes], filename: str = "") -> ParsedResume:
    """
    Parse a resume from a PDF or DOCX file (path or raw bytes).
    `filename` is required when passing bytes, so the file type can be
    determined (e.g. from a Streamlit UploadedFile.name).
    """
    name_hint = filename or (str(source) if isinstance(source, (str, Path)) else "")
    ext = Path(name_hint).suffix.lower()

    if ext == ".pdf":
        extraction = extract_text_from_pdf(source)
        parsed = parse_resume_text(extraction.text)
        parsed.file_type = "pdf"
        parsed.has_images = extraction.has_images
        parsed.has_tables = extraction.has_tables
        parsed.page_count = extraction.page_count
        parsed.layout_warnings = extraction.warnings
    elif ext == ".docx":
        extraction = extract_text_from_docx(source)
        parsed = parse_resume_text(extraction.text)
        parsed.file_type = "docx"
        parsed.has_images = extraction.has_images
        parsed.has_tables = extraction.has_tables
        parsed.layout_warnings = extraction.warnings
    else:
        raise ValueError(
            f"Unsupported file type '{ext}'. Only .pdf and .docx are supported."
        )

    return parsed


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parsed = parse_resume_file(sys.argv[1])
        print(f"Name: {parsed.name}")
        print(f"Email: {parsed.email}")
        print(f"Phone: {parsed.phone}")
        print(f"LinkedIn: {parsed.linkedin}")
        print(f"Sections found: {list(parsed.sections.keys())}")
        print(f"Bullet points found: {len(parsed.bullet_points)}")
        print(f"Word count: {parsed.word_count}")
        if parsed.layout_warnings:
            print("Warnings:", parsed.layout_warnings)
