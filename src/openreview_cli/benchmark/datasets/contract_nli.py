"""ContractNLI dataset loader.

3-class NLI (entailment/contradiction/neutral).
Raw HTTP+JSON download.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

CONTRACT_NLI_URL = (
    "https://huggingface.co/datasets/nguyenlab/ContractNLI/resolve/main/contract_nli_data.json"
)
CONTRACT_NLI_VERSION = "v1"

NLI_CLASSES = {"entailment", "contradiction", "neutral"}


def load_contract_nli_dataset(
    cache_dir: str | Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Load ContractNLI dataset, downloading if not cached.

    Yields per-example dicts with:
      - example_id: str
      - document_text: str
      - hypothesis: str (the NLI hypothesis)
      - ground_truth: dict with 'label' str (entailment/contradiction/neutral)
    """
    cache_path: str | Path | None = None
    if cache_dir:
        cache_path = Path(cache_dir) / "contract_nli_data.json"
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
            yield from _parse_contract_nli(data)
            return

    response = httpx.get(CONTRACT_NLI_URL, timeout=300, follow_redirects=True)
    response.raise_for_status()
    data = response.json()

    if cache_dir and cache_path:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
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
        yield {
            "example_id": doc_id,
            "document_text": doc_text,
            "hypothesis": hypothesis,
            "ground_truth": {"label": label},
        }
