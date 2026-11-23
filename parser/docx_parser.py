"""
docx_parser.py
--------------
Extracts text and layout signals from .docx resumes using python-docx.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass
class DOCXExtractionResult:
    text: str
    has_images: bool = False
    has_tables: bool = False
    table_count: int = 0
    has_headers_footers: bool = False
    warnings: list = field(default_factory=list)


def extract_text_from_docx(source: Union[str, Path, bytes]) -> DOCXExtractionResult:
    """
    Extract text and layout signals from a .docx resume.

    `source` can be a file path (str/Path) or raw bytes.
    Tables are included in the extracted text (row cells joined with " | ")
    since many resumes put skills or dates in tables, but a flag is also
    raised because tables are a common source of ATS parsing failures.
    """
    import docx

    if isinstance(source, bytes):
        import io
        source = io.BytesIO(source)

    try:
        document = docx.Document(source)
    except Exception as e:
        return DOCXExtractionResult(text="", warnings=[f"Failed to open .docx: {e}"])

    text_parts = [p.text for p in document.paragraphs if p.text.strip()]

    table_count = len(document.tables)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                text_parts.append(" | ".join(cells))

    # Detect embedded images via the document's relationship parts
    has_images = any("image" in rel.target_ref for rel in document.part.rels.values())

    # Detect header/footer content (ATS parsers frequently skip these entirely,
    # so contact info placed there can vanish)
    has_headers_footers = False
    for section in document.sections:
        header_text = " ".join(p.text for p in section.header.paragraphs).strip()
        footer_text = " ".join(p.text for p in section.footer.paragraphs).strip()
        if header_text or footer_text:
            has_headers_footers = True
            break

    warnings = []
    if has_headers_footers:
        warnings.append(
            "Content detected in a header/footer — many ATS parsers ignore "
            "these entirely, which can hide contact details."
        )
    if table_count > 0:
        warnings.append(
            f"{table_count} table(s) detected — tables can scramble reading "
            "order in some ATS parsers."
        )

    return DOCXExtractionResult(
        text="\n".join(text_parts).strip(),
        has_images=has_images,
        has_tables=table_count > 0,
        table_count=table_count,
        has_headers_footers=has_headers_footers,
        warnings=warnings,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = extract_text_from_docx(sys.argv[1])
        print(f"Tables: {result.table_count} | Images: {result.has_images} | "
              f"Header/Footer content: {result.has_headers_footers}")
        if result.warnings:
            print("Warnings:", result.warnings)
        print("---\n" + result.text[:1000])
