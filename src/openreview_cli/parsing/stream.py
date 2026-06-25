from collections.abc import Iterator
from pathlib import Path

from openreview_cli.parsing.models import Clause, Document, ParseError


def _pdf_ends_with_eof(path: Path) -> bool:
    with open(path, "rb") as f:
        f.seek(0, 2)
        end = f.tell()
        if end < 10:
            return False
        f.seek(max(0, end - 10))
        tail = f.read()
        return b"%%EOF" in tail


def stream_clauses(path: str | Path) -> Iterator[Clause]:
    path = Path(path)

    if not path.exists():
        raise ParseError(
            exit_code=8,
            category="file_not_found",
            message=f"No file found at '{path}'.",
            action="Check the file path and try again.",
        )

    ext = path.suffix.lower()

    if ext not in (".pdf", ".docx"):
        raise ParseError(
            exit_code=8,
            category="unsupported_format",
            message=f"Format '{ext}' is not supported. Supported: .pdf, .docx",
            action="Provide a PDF or DOCX file.",
        )

    if path.stat().st_size == 0:
        raise ParseError(
            exit_code=8,
            category="empty",
            message="The file appears to be empty or unreadable.",
            action="Provide a non-empty document file.",
        )

    if ext == ".pdf" and not _pdf_ends_with_eof(path):
        raise ParseError(
            exit_code=8,
            category="corrupt",
            message="The file appears to be corrupt or truncated.",
            action="Provide a valid PDF file.",
        )

    if ext == ".pdf":
        from openreview_cli.parsing.pdf_parser import PdfParser

        yield from PdfParser(path).parse()
    elif ext == ".docx":
        from openreview_cli.parsing.docx_parser import DocxParser

        yield from DocxParser(path).parse()
    else:
        raise ParseError(
            exit_code=8,
            category="unsupported_format",
            message=f"Format '{ext}' is not supported. Supported: .pdf, .docx",
            action="Provide a PDF or DOCX file.",
        )


def parse_document(path: str | Path) -> tuple[Document, list[Clause]]:
    import time

    start = time.perf_counter()
    path = Path(path)
    clauses = list(stream_clauses(path))
    duration = time.perf_counter() - start

    ext = path.suffix.lower()
    fmt = "pdf" if ext == ".pdf" else "docx"
    page_count = max(c.source_page or 0 for c in clauses) + 1 if clauses else 1

    doc = Document(
        source_path=path,
        format=fmt,
        page_count=page_count,
        clause_count=len(clauses),
        parse_duration_seconds=duration,
        warnings=[],
    )
    return doc, clauses


def format_text(clauses: list[Clause], doc: Document | None = None) -> str:
    lines = []
    for c in clauses:
        indent = "  " * c.level
        title_part = f"  {c.title}" if c.title else ""
        source = f" (page {c.source_page})" if c.source_page is not None else ""
        lines.append(f"{indent}{c.id}{title_part}{source}")
        if len(c.text) > 200:
            lines.append(f"{indent}  {c.text[:200]}...")
        else:
            lines.append(f"{indent}  {c.text}")
        lines.append("")
    return "\n".join(lines)


def format_json(clauses: list[Clause]) -> str:
    import json

    data = []
    for c in clauses:
        data.append(
            {
                "id": c.id,
                "title": c.title,
                "text": c.text,
                "level": c.level,
                "parent_id": c.parent_id,
                "source_page": c.source_page,
                "source_paragraph": c.source_paragraph,
            }
        )
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_summary(doc: Document) -> str:
    return f"Parsed {doc.clause_count} clauses across {doc.page_count} pages in {doc.parse_duration_seconds:.2f}s"
