# ATS Resume Checker

A local tool that analyzes a resume (PDF or DOCX) against a job description
and reports how it's likely to fare with an Applicant Tracking System (ATS):
keyword match, formatting red flags, grammar issues, and bullet-point
rewrite suggestions — plus downloadable HTML/PDF reports.

## Project Structure

```
ATS/
├── parser/          # Extract text + structured fields from PDF/DOCX resumes
│   ├── pdf_parser.py
│   ├── docx_parser.py
│   └── resume_parser.py
├── scoring/          # Keyword matching, formatting checks, overall score
│   ├── keyword_match.py
│   ├── ats_score.py
│   └── formatting.py
├── ai/                # Grammar, rewrite & suggestion generation
│   ├── ai_client.py     (shared optional-Claude-API helper)
│   ├── grammar.py
│   ├── rewrite.py
│   └── suggestions.py
├── reports/           # Report generation
│   ├── html_report.py
│   └── pdf_report.py
├── ui/
│   └── app.py          # Streamlit web app
└── database/
    ├── skills.db              # SQLite: skills taxonomy + action verbs (pre-built)
    └── build_skills_db.py     # Script that generates skills.db — re-run to customize it
```

## Setup

Requires Python 3.10+.

```bash
cd ATS
pip install -r requirements.txt
```

## Running the app

```bash
streamlit run ui/app.py
```

This opens a browser tab at `http://localhost:8501`. Upload a resume, paste
a job description, and click **Analyze Resume**.

## How scoring works

The overall score (0-100) is a weighted blend:

| Component | Weight | What it checks |
|---|---|---|
| Keyword Match | 60% | How many of the job description's skills/keywords appear in the resume, using the taxonomy in `database/skills.db` plus a fallback heuristic for technical terms outside that list |
| Formatting & Structure | 40% | Tables, images, headers/footers, missing standard sections (Experience/Education/Skills), missing contact info, resume length |

This is a **heuristic estimate** modeled on well-documented ATS parsing
behavior (e.g. many real-world ATS platforms genuinely struggle with tables,
images, and headers/footers) — it is not a guarantee of how any specific
employer's actual ATS software will score a given resume, since those
systems are proprietary and vary.

## Optional: AI-enhanced feedback

By default, everything (grammar checks, bullet rewrite tips, suggestions)
runs on rule-based logic only — no API key, no setup, no cost. Turning on
**"Use AI-enhanced feedback"** in the sidebar additionally uses Claude to:

- Catch more nuanced grammar/tense/clarity issues
- Generate concrete rewritten versions of weak bullet points

To enable it:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=your-key-here   # Windows: set ANTHROPIC_API_KEY=your-key-here
```

If the key isn't set (or the `anthropic` package isn't installed), the app
automatically falls back to rule-based-only analysis — the checkbox just
won't do anything extra, and nothing breaks.

## Customizing the skills database

`database/skills.db` ships pre-built with ~150 common skills (programming
languages, frameworks, cloud/DevOps, soft skills, certifications, etc.) and
~65 tagged resume action verbs. To add your own:

1. Edit the `SKILLS` / `ACTION_VERBS` dictionaries in `database/build_skills_db.py`
2. Re-run it: `python database/build_skills_db.py` (this rebuilds `skills.db` from scratch)

## Using individual modules directly

Every module also runs standalone for quick testing, e.g.:

```bash
python parser/resume_parser.py path/to/resume.pdf
python scoring/ats_score.py
python ai/suggestions.py
```

## Notes & limitations

- Scanned/image-only PDFs contain no extractable text — the app will warn
  you rather than silently returning an empty analysis. Most real ATS
  systems have the same limitation, so this itself is useful signal.
- The "freeform keyword" fallback (for technical terms not in `skills.db`)
  is a heuristic based on capitalization/formatting patterns — it will
  occasionally miss obscure terms or catch a false positive. Review the
  matched/missing lists with judgment before rewriting a resume around them.
- This tool is meant to help you self-review a resume before submitting it,
  not to reverse-engineer or game any specific company's real ATS.
