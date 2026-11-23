"""
build_skills_db.py
-------------------
Builds (or rebuilds) database/skills.db — a small SQLite database used by the
scoring engine to recognize skills/keywords in resumes and job descriptions,
and to recognize strong vs. weak resume action verbs.

Run directly to (re)create the database:
    python database/build_skills_db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "skills.db"

# category -> list of (skill_name, comma_separated_aliases)
SKILLS = {
    "programming_language": [
        ("Python", "py"), ("JavaScript", "js,ecmascript"), ("TypeScript", "ts"),
        ("Java", ""), ("C++", "cpp,c plus plus"), ("C#", "csharp,c sharp"),
        ("C", ""), ("Go", "golang"), ("Rust", ""), ("Ruby", ""), ("PHP", ""),
        ("Swift", ""), ("Kotlin", ""), ("Scala", ""), ("R", ""), ("MATLAB", ""),
        ("SQL", ""), ("Bash", "shell scripting"), ("Perl", ""), ("Dart", ""),
        ("Objective-C", ""), ("Julia", ""),
    ],
    "framework_library": [
        ("React", "react.js,reactjs"), ("Angular", ""), ("Vue.js", "vue"),
        ("Node.js", "nodejs,node"), ("Express.js", "express"), ("Django", ""),
        ("Flask", ""), ("FastAPI", ""), ("Spring Boot", "spring"),
        (".NET", "dotnet"), ("Ruby on Rails", "rails"), ("Next.js", "nextjs"),
        ("TensorFlow", ""), ("PyTorch", ""), ("Keras", ""), ("Pandas", ""),
        ("NumPy", ""), ("Scikit-learn", "sklearn"), ("jQuery", ""),
        ("Bootstrap", ""), ("Tailwind CSS", "tailwind"), ("GraphQL", ""),
        ("Redux", ""), ("Laravel", ""),
    ],
    "database": [
        ("MySQL", ""), ("PostgreSQL", "postgres"), ("MongoDB", "mongo"),
        ("SQLite", ""), ("Redis", ""), ("Oracle Database", "oracle db"),
        ("Microsoft SQL Server", "mssql,sql server"), ("Cassandra", ""),
        ("DynamoDB", ""), ("Elasticsearch", ""), ("Firebase", ""),
        ("MariaDB", ""), ("Snowflake", ""),
    ],
    "cloud_devops": [
        ("AWS", "amazon web services"), ("Azure", "microsoft azure"),
        ("Google Cloud Platform", "gcp,google cloud"), ("Docker", ""),
        ("Kubernetes", "k8s"), ("Jenkins", ""), ("CI/CD", "continuous integration,continuous deployment"),
        ("Terraform", ""), ("Ansible", ""), ("Git", ""), ("GitHub", ""),
        ("GitLab", ""), ("Linux", ""), ("Nginx", ""), ("CloudFormation", ""),
        ("Prometheus", ""), ("Grafana", ""), ("Vagrant", ""),
    ],
    "data_analytics": [
        ("Excel", "microsoft excel"), ("Tableau", ""), ("Power BI", "powerbi"),
        ("Looker", ""), ("Data Visualization", ""), ("Machine Learning", "ml"),
        ("Deep Learning", ""), ("Natural Language Processing", "nlp"),
        ("Data Mining", ""), ("Statistical Analysis", "statistics"),
        ("A/B Testing", "ab testing"), ("ETL", "extract transform load"),
        ("Big Data", ""), ("Apache Spark", "spark"), ("Hadoop", ""),
        ("Data Warehousing", ""),
    ],
    "design_tools": [
        ("Figma", ""), ("Adobe Photoshop", "photoshop"), ("Adobe Illustrator", "illustrator"),
        ("Adobe XD", ""), ("Sketch", ""), ("InDesign", ""), ("Canva", ""),
        ("UI/UX Design", "ui design,ux design"), ("Wireframing", ""),
        ("Prototyping", ""),
    ],
    "business_tools": [
        ("Microsoft Office", "ms office"), ("Salesforce", ""), ("SAP", ""),
        ("Jira", ""), ("Confluence", ""), ("Slack", ""), ("Trello", ""),
        ("Asana", ""), ("QuickBooks", ""), ("HubSpot", ""),
        ("Google Analytics", ""), ("Zendesk", ""),
    ],
    "methodology": [
        ("Agile", ""), ("Scrum", ""), ("Kanban", ""), ("Waterfall", ""),
        ("Lean", ""), ("Six Sigma", ""), ("DevOps", ""), ("TDD", "test driven development"),
        ("Design Thinking", ""),
    ],
    "soft_skill": [
        ("Leadership", ""), ("Communication", ""), ("Teamwork", "collaboration"),
        ("Problem Solving", ""), ("Critical Thinking", ""), ("Time Management", ""),
        ("Project Management", ""), ("Adaptability", ""), ("Creativity", ""),
        ("Negotiation", ""), ("Conflict Resolution", ""), ("Mentoring", ""),
        ("Public Speaking", ""), ("Stakeholder Management", ""),
        ("Decision Making", ""), ("Attention to Detail", ""),
        ("Customer Service", ""), ("Cross-functional Collaboration", ""),
    ],
    "certification": [
        ("PMP", "project management professional"), ("CPA", "certified public accountant"),
        ("AWS Certified Solutions Architect", ""), ("Scrum Master", "csm"),
        ("CISSP", ""), ("CFA", "chartered financial analyst"), ("Six Sigma Black Belt", ""),
        ("ITIL", ""), ("Google Analytics Certified", ""),
    ],
}

# Resume action verbs, tagged strong (achievement/ownership language) vs weak
# (vague, passive, or filler). Used by ai/rewrite.py and ai/grammar.py.
ACTION_VERBS = {
    "strong": [
        "achieved", "accelerated", "architected", "automated", "built",
        "championed", "conceptualized", "consolidated", "created", "delivered",
        "designed", "devised", "directed", "drove", "engineered", "established",
        "exceeded", "executed", "expanded", "generated", "implemented",
        "improved", "increased", "initiated", "innovated", "launched", "led",
        "managed", "mentored", "negotiated", "optimized", "orchestrated",
        "overhauled", "pioneered", "produced", "reduced", "redesigned",
        "resolved", "restructured", "revamped", "scaled", "spearheaded",
        "standardized", "streamlined", "strengthened", "transformed",
        "unified", "upgraded",
    ],
    "weak": [
        "assisted", "handled", "worked on", "helped with", "responsible for",
        "involved in", "participated in", "did", "was part of", "tasked with",
        "dealt with", "in charge of", "familiar with", "exposed to",
        "duties included", "helped",
    ],
}


def build_database() -> Path:
    """Create skills.db from scratch (overwriting any existing file)."""
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            aliases TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE action_verbs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verb TEXT NOT NULL UNIQUE,
            strength TEXT NOT NULL CHECK(strength IN ('strong', 'weak'))
        )
    """)
    cur.execute("CREATE INDEX idx_skills_category ON skills(category)")
    cur.execute("CREATE INDEX idx_verbs_strength ON action_verbs(strength)")

    skill_rows = [
        (name, category, aliases)
        for category, items in SKILLS.items()
        for name, aliases in items
    ]
    cur.executemany(
        "INSERT INTO skills (name, category, aliases) VALUES (?, ?, ?)",
        skill_rows,
    )

    verb_rows = [
        (verb, strength)
        for strength, verbs in ACTION_VERBS.items()
        for verb in verbs
    ]
    cur.executemany(
        "INSERT INTO action_verbs (verb, strength) VALUES (?, ?)",
        verb_rows,
    )

    conn.commit()
    n_skills = cur.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    n_verbs = cur.execute("SELECT COUNT(*) FROM action_verbs").fetchone()[0]
    conn.close()

    print(f"Built {DB_PATH} — {n_skills} skills, {n_verbs} action verbs.")
    return DB_PATH


if __name__ == "__main__":
    build_database()
