"""CUAD dataset loader.

Downloads the CUAD dataset via raw HTTP+JSON (no datasets lib).
Character-offset ground-truth parsing per NeurIPS 2021 protocol.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

CUAD_URL = "https://huggingface.co/datasets/theatticusproject/cuad/resolve/main/cuad_data.json"
CUAD_VERSION = "v1"

# 41 CUAD clause types
CUAD_CATEGORIES = [
    "audit",
    "change_of_control",
    "anti_assignment",
    "affiliate_license",
    "affiliate_license_licensee",
    "all_caps",
    "cap_on_liability",
    "cap_on_liability_ex",
    "change_of_control",
    "confidentiality_of_agreement",
    "credit_rating_covenant",
    "cure_period",
    "domicile",
    "covenant_not_to_sue",
    "covenant_not_to_sue_ex",
    "debt_covenant",
    "escrow",
    "evergreen",
    "exclusivity",
    "expiration_date",
    "governing_law",
    "indemnification_cap",
    "indemnification_basket",
    "initial_term",
    "insurance",
    "insurance_cap",
    "ip_ownership",
    "irrevocable_offer",
    "joint_ip",
    "license_grant",
    "license_grant_ex",
    "liquidated_damages",
    "minimum_commitment",
    "most_favored_nation",
    "non_compete",
    "non_disparagement",
    "non_transfer",
    "non_transfer_allow",
    "notice_period",
    "notice_period_to_terminate",
    "post_term",
    "post_term_restriction",
    "price_adjustments",
    "price_escalation",
    "renewal_term",
    "revenue_profit_sharing",
    "right_of_first_refusal",
    "rofr_rofo",
    "salary_grade",
    "severability",
    "shift_of_liability",
    "shift_of_liability_cap",
    "specific_performance",
    "stock_restriction",
    "subordination",
    "successors",
    "termination_for_cause",
    "termination_for_convenience",
    "termination_rights",
    "third_party_beneficiary",
    "venue",
    "volume_restriction",
    "waiver_of_consequential_damages",
    "waiver_of_jury_trial",
    "warranty_duration",
]


def load_cuad_dataset(
    cache_dir: str | Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Load CUAD dataset, downloading if not cached.

    Yields per-example dicts with:
      - example_id: str
      - document_text: str
      - category: str (one of 41 clause types)
      - ground_truth_spans: list of (start_char, end_char)
      - is_positive: bool (whether the clause is present)
    """
    cache_path: str | Path | None = None
    if cache_dir:
        cache_path = Path(cache_dir) / "cuad_data.json"
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
            yield from _parse_cuad(data)
            return

    # Download if not cached
    response = httpx.get(CUAD_URL, timeout=300, follow_redirects=True)
    response.raise_for_status()
    data = response.json()

    if cache_dir and cache_path:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(data, f)

    yield from _parse_cuad(data)


def _parse_cuad(data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Parse raw CUAD JSON into standardized examples."""
    examples = data.get("data", [])
    for example in examples:
        doc_text = example.get("text", "")
        doc_id = example.get("id", str(hash(doc_text)))
        for annotation in example.get("annotations", []):
            category = annotation.get("label", "unknown")
            is_positive = annotation.get("is_positive", False)
            spans = annotation.get("spans", [])
            gt_spans = [(s.get("start", 0), s.get("end", 0)) for s in spans]
            yield {
                "example_id": f"{doc_id}_{category}",
                "document_text": doc_text,
                "category": category,
                "ground_truth_spans": gt_spans,
                "is_positive": is_positive,
            }
