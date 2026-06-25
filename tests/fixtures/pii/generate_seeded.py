import json
from pathlib import Path

HERE = Path(__file__).parent
AUTO_DIR = HERE / "seeded_contracts" / "auto"
MANUAL_DIR = HERE / "seeded_contracts" / "manual"

AUTO_DIR.mkdir(parents=True, exist_ok=True)
MANUAL_DIR.mkdir(parents=True, exist_ok=True)

# Sample templates to generate fake contracts
TEMPLATES = [
    "This Services Agreement is entered into by {party_a} and {party_b}. Representative {name_1} can be reached at {email_1} or {phone_1}. The address is {address_1}. Effective date of birth is {dob_1}. The amount is {amount_1}. Tax ID is {tax_id_1}. Bank account is {acct_1}. Passport ID is {id_1}. Registration number is {reg_1}.",
    "Employment Contract between {party_a} and employee {name_1}. Employee lives at {address_1}. Email: {email_1}, Phone: {phone_1}. Born on {dob_1}. Base salary of {amount_1}. EIN of company: {tax_id_1}. Bank account details: {acct_1}. Driver's License: {id_1}. Company registration: {reg_1}.",
    "NDAs are signed by {party_a} represented by {name_1} ({email_1}, {phone_1}). The primary office is {address_1}. The contract value is {amount_1}. Registered under {reg_1} with Tax ID {tax_id_1}.",
]


def generate_data() -> None:
    ground_truth = {}

    # Generate 25 auto files
    for i in range(1, 26):
        template = TEMPLATES[(i - 1) % len(TEMPLATES)]
        party_a = f"AutoCompanyA{i} Inc."
        party_b = f"AutoCompanyB{i} LLC"
        name_1 = f"AutoName{i} Smith"
        email_1 = f"auto_email_{i}@example.com"
        phone_1 = f"555-01{i:02d}"
        address_1 = f"{i}00 Auto Blvd, Suite {i}, San Francisco, CA 94107"
        dob_1 = f"19{70 + i % 30}-05-{1 + i % 28:02d}"
        amount_1 = f"${5000 * i:,}.00"
        tax_id_1 = f"{10 + i % 89:02d}-{7654321 - i:07d}"
        acct_1 = f"GB29NWBK601613319268{i:02d}"
        id_1 = f"DL{9876543 + i}"
        reg_1 = f"REG-{100000 + i}"

        text = template.format(
            party_a=party_a,
            party_b=party_b,
            name_1=name_1,
            email_1=email_1,
            phone_1=phone_1,
            address_1=address_1,
            dob_1=dob_1,
            amount_1=amount_1,
            tax_id_1=tax_id_1,
            acct_1=acct_1,
            id_1=id_1,
            reg_1=reg_1,
        )

        filename = f"auto_contract_{i}.txt"
        filepath = AUTO_DIR / filename
        filepath.write_text(text)

        # Save entities in ground truth
        rel_path = f"auto/{filename}"
        ground_truth[rel_path] = [
            {"value": party_a, "type": "ORGANIZATION"},
            {"value": name_1, "type": "PERSON"},
            {"value": email_1, "type": "EMAIL_ADDRESS"},
            {"value": phone_1, "type": "PHONE_NUMBER"},
            {"value": address_1, "type": "LOCATION"},
            {"value": dob_1, "type": "DATE_TIME"},
            {"value": amount_1, "type": "AMOUNT"},
            {"value": tax_id_1, "type": "TAX_ID"},
            {"value": acct_1, "type": "ACCT"},
            {"value": id_1, "type": "ID_DOCUMENT"},
            {"value": reg_1, "type": "REG_NUMBER"},
        ]
        if "{party_b}" in template:
            ground_truth[rel_path].append({"value": party_b, "type": "ORGANIZATION"})

    # Generate 25 manual files
    for i in range(1, 26):
        template = TEMPLATES[(i - 1) % len(TEMPLATES)]
        party_a = f"ManualCompanyA{i} Corp"
        party_b = f"ManualCompanyB{i} Ltd"
        name_1 = f"ManualName{i} Jones"
        email_1 = f"manual_email_{i}@example.com"
        phone_1 = f"555-02{i:02d}"
        address_1 = f"{i}00 Manual Road, Dover, DE 19901"
        dob_1 = f"19{60 + i % 40}-10-{1 + i % 28:02d}"
        amount_1 = f"${10000 * i:,}"
        tax_id_1 = f"{20 + i % 79:02d}-{6543210 - i:07d}"
        acct_1 = f"GB29NWBK601613319269{i:02d}"
        id_1 = f"PASSPORT{123456 + i}"
        reg_1 = f"REG-{200000 + i}"

        text = template.format(
            party_a=party_a,
            party_b=party_b,
            name_1=name_1,
            email_1=email_1,
            phone_1=phone_1,
            address_1=address_1,
            dob_1=dob_1,
            amount_1=amount_1,
            tax_id_1=tax_id_1,
            acct_1=acct_1,
            id_1=id_1,
            reg_1=reg_1,
        )

        filename = f"manual_contract_{i}.txt"
        filepath = MANUAL_DIR / filename
        filepath.write_text(text)

        rel_path = f"manual/{filename}"
        ground_truth[rel_path] = [
            {"value": party_a, "type": "ORGANIZATION"},
            {"value": name_1, "type": "PERSON"},
            {"value": email_1, "type": "EMAIL_ADDRESS"},
            {"value": phone_1, "type": "PHONE_NUMBER"},
            {"value": address_1, "type": "LOCATION"},
            {"value": dob_1, "type": "DATE_TIME"},
            {"value": amount_1, "type": "AMOUNT"},
            {"value": tax_id_1, "type": "TAX_ID"},
            {"value": acct_1, "type": "ACCT"},
            {"value": id_1, "type": "ID_DOCUMENT"},
            {"value": reg_1, "type": "REG_NUMBER"},
        ]
        if "{party_b}" in template:
            ground_truth[rel_path].append({"value": party_b, "type": "ORGANIZATION"})

    # Write ground truth JSON file
    (HERE / "seeded_contracts" / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2))
    print("Generated 50 seeded documents and ground_truth.json.")


if __name__ == "__main__":
    generate_data()
