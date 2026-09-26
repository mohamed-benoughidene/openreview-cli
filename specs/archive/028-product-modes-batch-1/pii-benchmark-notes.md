# PII Benchmark Notes — Product Modes Batch 1

> Documentation of typical PII entity types per mode, for use in benchmark
> evaluation and privacy-engineering reviews.
>
> **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md) | **Task**: T078

---

## 1. IndemnityCheck (Indemnification Agreements)

| PII Entity Type | Typical Occurrence | Example |
|-----------------|-------------------|---------|
| `PERSON` | Party names, indemnitors, indemnitees, representatives | "John Smith", "Acme Corp (via Jane Doe)" |
| `ORGANIZATION` | Company names of indemnifying/indemnified parties | "Acme Corporation", "Widgets Inc." |
| `EMAIL_ADDRESS` | Notice addresses, legal contact emails | "legal@acme.com" |
| `PHONE_NUMBER` | Business phone numbers for notice provisions | "(555) 123-4567" |
| `LOCATION` | Jurisdictions, governing law venues, notice addresses | "Delaware", "New York County" |
| `DATE_TIME` | Effective dates, survival periods, notice deadlines | "January 1, 2026", "within 30 days" |
| `NRP` | Titles of signing officers, legal roles | "Chief Legal Officer", "VP of Contracts" |
| `IP_ADDRESS` | Rare — may appear in technology-related indemnities | N/A |

**Risk level**: Medium — indemnification agreements frequently name individuals
and their organizational affiliations.

---

## 2. ConsultCheck (Consulting/Service Agreements)

| PII Entity Type | Typical Occurrence | Example |
|-----------------|-------------------|---------|
| `PERSON` | Consultant name, client representatives | "Jane Doe", "Project Sponsor: Bob" |
| `ORGANIZATION` | Consulting firm, client company | "Doe Consulting LLC", "MegaClient Corp" |
| `EMAIL_ADDRESS` | Point of contact, invoicing, notice addresses | "jane@doeconsulting.com" |
| `PHONE_NUMBER` | Business lines, emergency contacts | "+1-555-987-6543" |
| `LOCATION` | Place of performance, billing address | "San Francisco, CA" |
| `DATE_TIME` | Engagement period, invoicing dates, SOW timelines | "March 1 - August 31, 2026" |
| `NRP` | Role titles, functional titles | "Senior Consultant", "Engagement Manager" |
| `CREDIT_CARD` | Rare — only if payment method is specified in the agreement | N/A |

**Risk level**: High — consulting agreements contain extensive personal contact
information for both parties.

---

## 3. WorkCheck (Work-for-Hire / Independent Contractor Agreements)

| PII Entity Type | Typical Occurrence | Example |
|-----------------|-------------------|---------|
| `PERSON` | Contractor name, client hiring manager | "Alex Rivera", "Hiring: Sarah Chen" |
| `ORGANIZATION` | Contractor's business entity, client company | "Rivera Designs", "TechPlatform Inc." |
| `EMAIL_ADDRESS` | Communication channels, invoicing | "alex@riveradesigns.com" |
| `PHONE_NUMBER` | Contact numbers for urgent matters | "555-234-5678" |
| `LOCATION` | Work location, tax jurisdiction | "Remote — Austin, TX area" |
| `DATE_TIME` | Contract term, payment schedule, deadlines | "6-month term starting April 1" |
| `NRP` | Worker classification labels, role titles | "Independent Contractor", "Design Lead" |
| `SSN` / `TAX_ID` | **Critical** — IRS 1099 filing requires TIN/EIN | "XXX-XX-1234" (stripped) |
| `BANK_ACCOUNT` | Direct deposit information for payment | Rare — more common in payment addenda |

**Risk level**: **Very High** — work-for-hire agreements often contain tax
identifiers and direct financial information alongside personal contact data.

---

## 4. LOICheck (Letters of Intent / MOUs)

| PII Entity Type | Typical Occurrence | Example |
|-----------------|-------------------|---------|
| `PERSON` | Signing parties, board members, key executives | "Michael Chang", "CEO: Jane Smith" |
| `ORGANIZATION` | Buyer, seller, target company | "AcquireCorp", "TargetCo Ltd." |
| `EMAIL_ADDRESS` | Deal team contacts, legal counsel | "mchang@acquirecorp.com" |
| `PHONE_NUMBER` | Business numbers included in notice provisions | "(212) 555-0199" |
| `LOCATION` | Principal place of business, governing law | "Wilmington, DE" |
| `DATE_TIME` | Exclusivity periods, expiration dates, due diligence windows | "45-day exclusivity ending May 15" |
| `NRP` | Executive titles, board roles | "Chairman", "Chief Executive Officer" |
| `FINANCIAL` | Proposed valuation, breakup fees (not PII per se but sensitive) | "$5M breakup fee" |

**Risk level**: Medium — LOIs are less personal but contain business-sensitive
financial terms and executive identities.

---

## 5. SubCheck (Subcontractor Agreements)

| PII Entity Type | Typical Occurrence | Example |
|-----------------|-------------------|---------|
| `PERSON` | Subcontractor principal, prime contractor reps | "Maria Garcia", "GC Rep: Tom" |
| `ORGANIZATION` | Subcontractor company, prime contractor, owner | "Garcia Electric", "BuildRight General" |
| `EMAIL_ADDRESS` | Project communications, RFI contacts | "maria@garciainc.com" |
| `PHONE_NUMBER` | Site contacts, emergency numbers | "555-345-6789" |
| `LOCATION` | Project site address, offices | "123 Construction Way, Phoenix AZ" |
| `DATE_TIME` | Construction schedule, payment milestones | "Completion by July 30, 2026" |
| `NRP` | Trade roles, licensing identifiers | "Licensed Electrician #12345" |
| `BANK_ACCOUNT` | Payment disbursement info | Rare — in payment terms sections |
| `LICENSE_ID` | Professional/trade license numbers | "Contractor Lic. #C-123456" |

**Risk level**: High — subcontractor agreements often include field-level
personnel names, site addresses, and trade license numbers.

---

## 6. SettlementCheck (Settlement & Release Agreements)

| PII Entity Type | Typical Occurrence | Example |
|-----------------|-------------------|---------|
| `PERSON` | Claimant, respondent, counsel, witnesses | "Plaintiff: James Wilson", "Defendant: CorpX" |
| `ORGANIZATION` | Corporate parties, insurance carriers, law firms | "BigLaw LLP", "InsureCo" |
| `EMAIL_ADDRESS` | Counsel communications, payment notifications | "jwilson@claimantlaw.com" |
| `PHONE_NUMBER` | Counsel contact, party contact | "555-456-7890" |
| `LOCATION` | Governing law, venue for enforcement | "Superior Court of California" |
| `DATE_TIME` | Effective date, payment schedule, release deadlines | "Effective: June 1, 2026" |
| `NRP` | Legal roles, party designations | "Plaintiff", "Respondent", "Counsel of Record" |
| `FINANCIAL` | Settlement amounts, payment terms (sensitive business data) | "$250,000 lump sum" |
| `SSN` / `TAX_ID` | IRS reporting for settlement payments (Form 1099) | Sometimes present |

**Risk level**: **Very High** — settlement agreements combine personal
identification, legal representation details, financial terms, and sometimes
tax identifiers. Confidentiality clauses may also reference the existence of
the settlement itself, which is a PII-adjacent sensitivity.

---

## Summary: PII Density by Mode

| Mode | PII Risk | Key Entity Types |
|------|----------|-----------------|
| IndemnityCheck | Medium | PERSON, ORG, EMAIL, LOCATION, DATE |
| ConsultCheck | High | PERSON, ORG, EMAIL, PHONE, LOCATION, DATE |
| WorkCheck | **Very High** | PERSON, ORG, EMAIL, PHONE, SSN/TAX_ID, BANK_ACCOUNT |
| LOICheck | Medium | PERSON, ORG, EMAIL, DATE, FINANCIAL |
| SubCheck | High | PERSON, ORG, EMAIL, PHONE, LOCATION, LICENSE_ID |
| SettlementCheck | **Very High** | PERSON, ORG, EMAIL, PHONE, SSN/TAX_ID, FINANCIAL |

All modes must use the existing PII stripping engine (Presidio-based) with the
same 16-entity-type recognizer set before any external AI Gateway call. No
per-mode PII configuration is needed — the existing engine covers all entity
types listed above.
