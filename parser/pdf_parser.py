"""
pdf_parser.py
-------------
Extracts text (and light layout signals) from PDF resumes.

Primary engine: pdfplumber (better at preserving reading order / spacing,
which matters a lot for resumes with multi-column layouts).
Fallback engine: pypdf (faster, more tolerant of malformed PDFs).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass
class PDFExtractionResult:
    text: str
    page_count: int = 0
    has_images: bool = False
    has_tables: bool = False
    engine_used: str = ""
    warnings: list = field(default_factory=list)


def _extract_with_pdfplumber(source) -> PDFExtractionResult:
    import pdfplumber

    text_parts = []
    has_images = False
    has_tables = False

    with pdfplumber.open(source) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

            if page.images:
                has_images = True
            if page.find_tables():
                has_tables = True

    return PDFExtractionResult(
        text="\n".join(text_parts).strip(),
        page_count=page_count,
        has_images=has_images,
        has_tables=has_tables,
        engine_used="pdfplumber",
    )


def _extract_with_pypdf(source) -> PDFExtractionResult:
    from pypdf import PdfReader

    reader = PdfReader(source)
    text_parts = [page.extract_text() or "" for page in reader.pages]

    return PDFExtractionResult(
        text="\n".join(text_parts).strip(),
        page_count=len(reader.pages),
        has_images=False,  # pypdf image detection is unreliable enough to skip
        has_tables=False,
        engine_used="pypdf",
        warnings=["Used fallback parser (pypdf); image/table detection skipped."],
    )


def extract_text_from_pdf(source: Union[str, Path, bytes]) -> PDFExtractionResult:
    """
    Extract text and basic layout signals from a PDF resume.

    `source` can be a file path (str/Path) or raw bytes (e.g. an uploaded
    file's .getvalue() from Streamlit).

    Tries pdfplumber first; falls back to pypdf if pdfplumber fails or
    returns suspiciously little text (e.g. a scanned/image-only PDF).
    """
    if isinstance(source, bytes):
        import io
        source = io.BytesIO(source)

    try:
        result = _extract_with_pdfplumber(source)
        if len(result.text.strip()) < 20:
            result.warnings.append(
                "Very little text extracted — this PDF may be a scanned image "
                "rather than real text, which most ATS systems cannot read at all."
            )
        return result
    except Exception as e:
        # Reset stream position if we're working with an in-memory buffer
        if hasattr(source, "seek"):
            source.seek(0)
        try:
            result = _extract_with_pypdf(source)
            result.warnings.append(f"pdfplumber failed ({e}); used pypdf fallback.")
            return result
        except Exception as e2:
            return PDFExtractionResult(
                text="",
                warnings=[f"Both PDF parsers failed. pdfplumber: {e} | pypdf: {e2}"],
            )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = extract_text_from_pdf(sys.argv[1])
        print(f"Engine: {result.engine_used} | Pages: {result.page_count}")
        print(f"Has images: {result.has_images} | Has tables: {result.has_tables}")
        if result.warnings:
            print("Warnings:", result.warnings)
        print("---\n" + result.text[:1000])
