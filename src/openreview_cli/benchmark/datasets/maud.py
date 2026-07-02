"""MAUD dataset loader.

92 questions grouped into 39 deal-point categories.
Raw HTTP+JSON download, binary classification ground truth.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

MAUD_URL = "https://huggingface.co/datasets/theatticusproject/maud/resolve/main/maud_data.json"
MAUD_VERSION = "v1"

# The 39 MAUD deal-point categories
MAUD_CATEGORIES = [
    "acquisition_type",
    "additional_buyer_protections",
    "additional_seller_protections",
    "adjustment_mechanism",
    "anti_sandbagging",
    "basket",
    "basket_cap_structure",
    "baskets",
    "bring_down",
    "cap",
    "captive_issuer_exception",
    "carveout_to_the_definition_of_change",
    "collateral",
    "consequential_damages",
    "cooperation",
    "covenant_not_to_sue",
    "cure_period",
    "data_room_completeness",
    "de_minimis",
    "definition_of_change",
    "earnout",
    "effective_date",
    "environmental",
    "equity_commitment_letter",
    "escrow",
    "exchange_act_reports",
    "exclusivity",
    "fidelity_bond",
    "financial_statements",
    "general_indemnification",
    "indemnification_cap",
    "indemnification_escrow",
    "indemnification_period",
    "insurance",
    "inter_seller",
    "knowledge_definition",
    "labor_related",
    "larger_related_transaction",
    "legal_proceedings",
    "liability_for_brokers_fees",
    "material_adverse_change",
    "material_contracts",
    "non_compete",
    "no_shop",
    "ordinary_course",
    "other_indemnification",
    "other_indemnification_baskets",
    "ownership_of_assets",
    "permitted_disclosures",
    "plug",
    "preparation_of_financial_statements",
    "public_filing",
    "purchase_price_adjustment",
    "regulatory_filings",
    "reimbursement_of_brokers_fees",
    "representations_and_warranties",
    "retention_of_assets",
    "right_of_first_refusal",
    "sale_of_assets",
    "schedules",
    "section_409a",
    "securities_law_compliance",
    "security_holder_approval",
    "seller_employee",
    "seller_pension",
    "seller_tax_representations",
    "solvency",
    "specific_performance",
    "standstill",
    "stockholder_meeting",
    "subsequent_offering",
    "subscription_rights",
    "survival_period",
    "survival_period_indemnification",
    "survival_period_representations_and_warranties",
    "tax_asset_protection",
    "tax_contest",
    "tax_indemnification",
    "tax_representations_and_warranties",
    "termination",
    "third_party_consent",
    "third_party_consent_buyer",
    "title_to_assets",
    "transaction_type",
    "transfer_of_ownership_of_shares",
    "update_of_schedules",
    "voting_restrictions",
    "waiver_of_jury_trial",
]


def load_maud_dataset(
    cache_dir: str | Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Load MAUD dataset, downloading if not cached.

    Yields per-example dicts with:
      - example_id: str
      - document_text: str
      - category: str (deal-point category)
      - ground_truth: dict with 'match' bool
    """
    cache_path: str | Path | None = None
    if cache_dir:
        cache_path = Path(cache_dir) / "maud_data.json"
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
            yield from _parse_maud(data)
            return

    response = httpx.get(MAUD_URL, timeout=300, follow_redirects=True)
    response.raise_for_status()
    data = response.json()

    if cache_dir and cache_path:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(data, f)

    yield from _parse_maud(data)


def _parse_maud(data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Parse raw MAUD JSON into standardized examples."""
    examples = data.get("data", [])
    for example in examples:
        doc_text = example.get("text", "")
        doc_id = example.get("id", str(hash(doc_text)))
        for annotation in example.get("annotations", []):
            category = annotation.get("label", "unknown")
            match = annotation.get("match", False)
            yield {
                "example_id": f"{doc_id}_{category}",
                "document_text": doc_text,
                "category": category,
                "ground_truth": {"match": match},
            }
