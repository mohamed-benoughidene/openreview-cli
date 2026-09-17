"""ContractNLI dataset loader.

3-class NLI (entailment/contradiction/neutral) and LegalBench-RAG NDA benchmark support.
Supports local data/legalbenchrag loading and raw HTTP+JSON download fallback.
"""

import json
import urllib.parse
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

CONTRACT_NLI_URL = (
    "https://huggingface.co/datasets/nguyenlab/ContractNLI/resolve/main/contract_nli_data.json"
)
CONTRACT_NLI_VERSION = "v1"

NLI_CLASSES = {"entailment", "contradiction", "neutral"}

# Mapping ContractNLI NDA hypothesis questions to PreCheck playbook categories
HYPOTHESIS_CATEGORY_MAP: dict[str, str] = {
    "acquire information similar": "permitted-disclosures",
    "independently develop": "permitted-disclosures",
    "share some confidential information with their employees": "permitted-disclosures",
    "share some confidential information with third parties": "permitted-disclosures",
    "verbally conveyed information": "confidentiality-term",
    "disclosing the fact that the agreement was agreed": "boilerplate",
    "prohibits the receiving party from soliciting": "non-solicitation",
    "does not grant the receiving party any rights": "boilerplate",
    "obligations of the agreement may survive": "confidentiality-term",
    "reverse engineer": "permitted-disclosures",
    "create a copy": "return-of-materials",
    "retain some confidential information": "return-of-materials",
    "expressly identified": "confidentiality-term",
    "required by law": "permitted-disclosures",
    "restrict the use of confidential information": "permitted-disclosures",
    "destroy or return confidential information": "return-of-materials",
    "only include technical information": "confidentiality-term",
}


def map_hypothesis_to_category(hypothesis: str) -> str:
    """Map a ContractNLI query/hypothesis to a standard precheck playbook category."""
    for pattern, category in HYPOTHESIS_CATEGORY_MAP.items():
        if pattern.lower() in hypothesis.lower():
            return category
    return "confidentiality-term"


def _find_local_legalbenchrag_dir(data_dir: str | Path | None = None) -> Path | None:
    """Check candidate paths for local LegalBench-RAG dataset."""
    candidates: list[Path] = []
    if data_dir:
        candidates.append(Path(data_dir))
    candidates.extend(
        [
            Path.cwd() / "data" / "legalbenchrag",
            Path(__file__).resolve().parents[4] / "data" / "legalbenchrag",
            Path("/tmp/opencode/legalbenchrag_data"),
        ]
    )
    for candidate in candidates:
        if (candidate / "benchmarks" / "contractnli.json").exists():
            return candidate
    return None


def load_contract_nli_dataset(
    cache_dir: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Load ContractNLI dataset from local LegalBench-RAG corpus, cache, or download.

    Yields per-example dicts with:
      - example_id: str
      - document_text: str
      - hypothesis: str (the NLI hypothesis)
      - category: str (mapped playbook category)
      - ground_truth: dict with 'label' str (entailment/contradiction/neutral)
      - ground_truth_spans: list of (start_char, end_char)
      - file_path: optional str relative path to source document
    """
    # 1. Try local LegalBench-RAG dataset first (no network needed)
    local_dir = _find_local_legalbenchrag_dir(data_dir)
    if local_dir:
        bench_file = local_dir / "benchmarks" / "contractnli.json"
        corpus_dir = local_dir / "corpus"
        with open(bench_file, encoding="utf-8") as f:
            bench_data = json.load(f)

        tests = bench_data.get("tests", [])
        for idx, test in enumerate(tests):
            query = test.get("query", "")
            category = map_hypothesis_to_category(query)
            snippets = test.get("snippets", [])
            for s_idx, snippet in enumerate(snippets):
                rel_path = snippet.get("file_path", "")
                span = snippet.get("span", [0, 0])
                answer = snippet.get("answer", "")

                doc_text = ""
                # Resolve file path (handling URL encoded filenames like %20)
                for candidate_name in [rel_path, urllib.parse.unquote(rel_path)]:
                    target_file = corpus_dir / candidate_name
                    if target_file.exists():
                        doc_text = target_file.read_text(encoding="utf-8", errors="replace")
                        break

                yield {
                    "example_id": f"contractnli_{idx}_{s_idx}_{Path(rel_path).stem}",
                    "document_text": doc_text,
                    "hypothesis": query,
                    "category": category,
                    "ground_truth_spans": [(span[0], span[1])],
                    "ground_truth_answer": answer,
                    "ground_truth": {"label": "entailment"},
                    "file_path": rel_path,
                }
        return

    # 2. Try cache
    cache_path: str | Path | None = None
    if cache_dir:
        cache_path = Path(cache_dir) / "contract_nli_data.json"
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            yield from _parse_contract_nli(data)
            return

    # 3. HTTP Download fallback
    response = httpx.get(CONTRACT_NLI_URL, timeout=300, follow_redirects=True)
    response.raise_for_status()
    data = response.json()

    if cache_dir and cache_path:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    yield from _parse_contract_nli(data)


def _parse_contract_nli(data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Parse raw ContractNLI JSON into standardized examples."""
    examples = data.get("data", [])
    for example in examples:
        doc_text = example.get("text", "")
        hypothesis = example.get("hypothesis", "")
        doc_id = example.get("id", str(hash(doc_text)))
        label = example.get("label", "neutral")
        if label not in NLI_CLASSES:
            label = "neutral"
        category = map_hypothesis_to_category(hypothesis)
        yield {
            "example_id": doc_id,
            "document_text": doc_text,
            "hypothesis": hypothesis,
            "category": category,
            "ground_truth": {"label": label},
            "ground_truth_spans": [],
        }
