import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from openreview_cli.parsing.models import Clause


def extract_page_text(page: Any) -> str:
    blocks = page.get_text("dict", sort=True).get("blocks", [])
    text_parts: list[str] = []
    for block in blocks:
        if block.get("type") == 0:
            for line in block.get("lines", []):
                line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                text_parts.append(line_text)
    return "\n".join(text_parts) + "\n"


def detect_headings_from_toc(toc: list[list[Any]]) -> list[tuple[int, str, int]]:
    return [(entry[0], entry[1], entry[2] - 1) for entry in toc]


def extract_font_properties(span: dict[str, Any]) -> dict[str, Any]:
    flags = span.get("flags", 0)
    return {
        "bold": bool(flags & 16),
        "size": span.get("size", 0),
        "font": span.get("font", ""),
    }


class PdfParser:
    def __init__(self, path: Path) -> None:
        self.path = path

    def parse(self) -> Iterator[Clause]:
        import pymupdf

        from openreview_cli.parsing.clause_detector import (
            build_hierarchy,
            detect_clause_starts,
            nupunkt_detect_boundaries,
        )
        from openreview_cli.parsing.models import ParseError

        try:
            doc: Any = pymupdf.open(str(self.path))  # type: ignore[no-untyped-call]
        except Exception:
            raise ParseError(
                exit_code=8,
                category="corrupt",
                message="The file appears to be corrupt or truncated.",
                action="Provide a valid PDF file.",
            ) from None

        if doc.needs_pass:
            password = os.environ.get("OPENREVIEW_PDF_PASSWORD")
            if password:
                try:
                    doc.authenticate(password)
                except Exception:
                    doc.close()
                    raise ParseError(
                        exit_code=8,
                        category="password_protected",
                        message="This contract is password-protected.",
                        action="The password in OPENREVIEW_PDF_PASSWORD was incorrect. Set the correct password or provide an unlocked copy.",
                    ) from None
            elif sys.stdin.isatty():
                import getpass

                try:
                    password = getpass.getpass("PDF password: ")
                    doc.authenticate(password)
                except Exception:
                    doc.close()
                    raise ParseError(
                        exit_code=8,
                        category="password_protected",
                        message="This contract is password-protected.",
                        action="Incorrect password. Try again or provide an unlocked copy.",
                    ) from None
            else:
                doc.close()
                raise ParseError(
                    exit_code=8,
                    category="password_protected",
                    message="This contract is password-protected.",
                    action="Enter the password or provide an unlocked copy.",
                )

        toc = doc.get_toc()
        headings = detect_headings_from_toc(toc) if toc else []

        try:
            clause_counter = 0
            has_text = False

            for page_num, page in enumerate(doc):
                try:
                    page_text = extract_page_text(page)
                except Exception:
                    raise ParseError(
                        exit_code=8,
                        category="corrupt",
                        message="The file appears to be corrupt or truncated.",
                        action="Provide a valid PDF file.",
                    ) from None

                if page_text.strip():
                    has_text = True
                    boundaries = nupunkt_detect_boundaries(page_text)
                    clause_starts = detect_clause_starts(page_text)
                    clauses = build_hierarchy(
                        boundaries, clause_starts, headings, page_num, clause_counter, page_text
                    )
                    for clause in clauses:
                        if clause.id:
                            clause_counter += 1
                        yield clause

            if not has_text:
                raise ParseError(
                    exit_code=8,
                    category="no_text",
                    message="This PDF contains no extractable text. If it is a scanned document, install the OCR extension: openreview install ocr",
                    action="Install OCR extension or provide a text-based PDF.",
                )

        except GeneratorExit:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            doc.close()
