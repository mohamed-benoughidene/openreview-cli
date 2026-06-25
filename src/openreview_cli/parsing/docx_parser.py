from collections.abc import Iterator
from pathlib import Path
from typing import Any

from openreview_cli.parsing.models import Clause

_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def get_heading_level(paragraph: Any) -> int | None:
    style_name = paragraph.style.name if paragraph.style else ""
    if style_name.startswith("Heading "):
        parts = style_name.split()
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1]) - 1
    return None


def detect_tracked_changes(doc: Any) -> bool:
    body = doc.element.body
    ins = list(body.iter(f"{{{_WORD_NS}}}ins"))
    dels = list(body.iter(f"{{{_WORD_NS}}}del"))
    return bool(ins) or bool(dels)


def skip_embedded_images(paragraphs: Any) -> Iterator[Any]:
    for para in paragraphs:
        if para._p.findall(f".//{{{_WORD_NS}}}drawing"):
            continue
        yield para


class DocxParser:
    def __init__(self, path: Path):
        self.path = path

    def parse(self) -> Iterator[Clause]:
        from docx import Document

        try:
            doc = Document(str(self.path))
        except Exception:
            from openreview_cli.parsing.models import ParseError

            raise ParseError(
                exit_code=8,
                category="corrupt",
                message="The file appears to be corrupt or truncated.",
                action="Provide a valid DOCX file.",
            ) from None

        from openreview_cli.parsing.clause_detector import (
            detect_clause_starts,
            nupunkt_detect_boundaries,
        )

        detect_tracked_changes(doc)
        paras = list(skip_embedded_images(doc.paragraphs))

        all_text = ""
        para_offsets = []
        heading_boundaries = []

        try:
            for para_idx, para in enumerate(paras):
                text = para.text.strip()
                if not text:
                    continue
                offset = len(all_text)
                heading_level = get_heading_level(para)
                if heading_level is not None:
                    heading_boundaries.append((offset, heading_level, text))
                para_offsets.append((offset, text, para_idx))
                all_text += text + "\n"

            nupunkt_detect_boundaries(all_text)
            clause_starts = detect_clause_starts(all_text)

            if not clause_starts and not heading_boundaries:
                for start_offset, text, para_idx in para_offsets:
                    yield Clause(
                        id=f"clause-{para_idx}",
                        title=None,
                        text=text,
                        level=0,
                        parent_id=None,
                        source_page=None,
                        source_paragraph=para_idx,
                        source_span=(start_offset, start_offset + len(text)),
                    )
                return

            cuts = sorted({cs[0] for cs in clause_starts} | {hb[0] for hb in heading_boundaries})

            if not cuts:
                cuts = [0]

            cut_positions = sorted(cuts)
            for i, cut in enumerate(cut_positions):
                end = cut_positions[i + 1] if i + 1 < len(cut_positions) else len(all_text)
                span_text = all_text[cut:end].strip()
                if not span_text:
                    continue

                heading_match = [hb for hb in heading_boundaries if hb[0] == cut]
                title = heading_match[0][2] if heading_match else None
                level = heading_match[0][1] if heading_match else 0

                matching_paras = [(o, t, pi) for (o, t, pi) in para_offsets if o >= cut and o < end]
                first_para_idx = matching_paras[0][2] if matching_paras else 0

                yield Clause(
                    id=f"clause-{i}",
                    title=title,
                    text=span_text,
                    level=level,
                    parent_id=None,
                    source_page=None,
                    source_paragraph=first_para_idx,
                    source_span=(cut, end),
                )

        except GeneratorExit:
            pass
        except KeyboardInterrupt:
            pass
