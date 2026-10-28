# Freelancer Contract Review — Current Design Baseline

## Underlying Idea

> Build contract review as a sequence of isolated AI workers that never share conversational memory; they communicate only by depositing and consuming explicit, structured review artifacts from a mailbox.

---

## Where We Are Now

### 1. Review Algorithm

The agreed conceptual review algorithm is:

```text
MATCH
  ↓
EXTRACT
  ↓
ASSESS
  ↓
VERIFY
  ↓
SYNTHESIZE
```

#### MATCH

Find the contract content relevant to the review playbook.

This includes two kinds of matching:

- **Positive matching:** identify clauses/provisions that correspond to review rules.
- **Negative matching:** identify expected protections or requirements for which no evidence is found.

#### EXTRACT

Extract the factual information needed for evaluation.

The extractor should preserve evidence from the contract and turn it into structured facts rather than jumping directly to a judgment.

Examples:

- Parties
- Dates
- Notice periods
- Payment amounts and schedules
- Liability caps
- Indemnity obligations
- IP ownership/licensing
- Confidentiality obligations
- Termination rights
- Definitions and cross-references

#### ASSESS

Compare the extracted facts against the freelancer's playbook.

Possible outcomes can include:

- Preferred
- Acceptable
- Negotiable
- Dangerous
- Walk-away
- Missing protection

The assessment should identify the applicable playbook rule, the relevant evidence, and the reason for the classification.

#### VERIFY

Independently check whether the assessment is actually supported by:

- the original contract language,
- the extracted facts,
- and the applicable playbook rule.

The verifier should be able to reject or flag a previous assessment rather than simply agree with it.

Possible verification outcomes:

- Valid
- Rejected / unsupported
- Ambiguous / human review required

#### SYNTHESIZE

Combine clause-level findings into contract-level conclusions.

This stage is necessary because separate clauses can interact.

Examples:

- Termination + payment + unfinished-work provisions
- Indemnity + liability cap + carve-outs
- IP ownership + payment + termination
- Confidentiality/data + liability
- Scope + acceptance + payment

The goal is to detect combined risks, contradictions, dependencies, and interactions that cannot reliably be identified by reviewing each clause in isolation.

---

## 2. Review Ontology

The agreed review ontology is the set of domains the system should know how to inspect.

### 1. Parties & Authority

Check:

- Legal names
- Jurisdictions
- Signer identity and authority
- Party relationships

Potential concerns:

- Wrong entity
- Missing party information
- Unauthorized signer

### 2. Scope

Check:

- Goods/services/license
- Deliverables
- Specific and measurable requirements
- Exclusions
- Acceptance criteria where relevant

Potential concerns:

- Vague scope
- Undefined deliverables
- Terms that allow underdelivery or uncontrolled scope expansion

### 3. Price & Payment

Check:

- Total price
- Payment schedule
- Invoicing
- Late fees
- Price increases
- Currency and other material payment mechanics

Potential concerns:

- Surprise fees
- Delayed payment
- Unclear payment triggers
- Margin loss

### 4. Term & Renewal

Check:

- Start date
- Initial term
- Renewal terms
- Renewal frequency
- Notice windows
- Notice deadlines

Potential concerns:

- Auto-renewal
- Long notice periods
- Easy-to-miss renewal deadlines

### 5. Risk Allocation

Check:

- Indemnification
- Limitation of liability
- Liability caps
- Carve-outs
- Warranties
- Related exposure terms

Potential concerns:

- Uncapped exposure
- Broad indemnity triggers
- One-sided indemnity
- Liability carve-outs that materially weaken the cap

This domain is highly cross-clause and should receive strong treatment during SYNTHESIZE.

### 6. Confidentiality & Data

Check:

- Definition of confidential information
- Permitted uses
- Disclosure restrictions
- Duration
- Data handling obligations
- Relevant privacy/security obligations

Potential concerns:

- Overly weak confidentiality
- Broad data-use rights
- Privacy or security exposure

### 7. Intellectual Property

Check:

- Ownership of work product
- Assignment
- Licenses granted
- License scope
- Survival after termination
- Relevant restrictions

Potential concerns:

- Overbroad ownership transfer
- Unintended rights over freelancer materials/data
- Grants surviving beyond the intended relationship

### 8. Exit

Check:

- Termination rights
- Termination for convenience
- Notice periods
- Cure periods
- Early-exit fees
- Assignment restrictions
- Governing law
- Dispute resolution
- Change-of-control triggers
- Survival provisions

Potential concerns:

- No practical exit
- Long cure periods
- Expensive early exit
- One-sided termination rights

### 9. Mechanical / Integrity Check

Check:

- Cross-references
- Defined terms
- Attached exhibits
- Conflicting provisions
- Assignment clauses
- Change-of-control triggers
- Survival clauses
- Missing or broken references

This is primarily a document-integrity layer rather than a substantive risk category.

---

## 3. Execution Architecture

The agreed execution architecture is:

```text
Fresh LLM Session
        ↓
Structured Artifact
        ↓
Mailbox
        ↓
Fresh LLM Session
        ↓
Structured Artifact
        ↓
Mailbox
        ↓
...
```

### Core Principle

> **Fresh context. Explicit state. Specialized work. Independent verification.**

Each worker:

1. Starts with a fresh context.
2. Receives only the artifacts required for its task.
3. Performs one defined job.
4. Produces a structured artifact.
5. Places the artifact in the mailbox for the next stage.

Workers do **not** rely on hidden conversational memory from previous workers.

### Mailbox Concept

The mailbox is conceptually a:

- Job queue
- Artifact handoff mechanism
- Persistent state boundary

It should contain typed artifacts rather than unrestricted AI prose.

Examples of artifact types:

```text
ContractArtifact
ClauseArtifact
MatchArtifact
ExtractionArtifact
AssessmentArtifact
VerificationArtifact
CrossClauseFinding
FinalRecommendation
```

---

## 4. Important Design Decisions

### Decision: Keep the review algorithm

```text
MATCH → EXTRACT → ASSESS → VERIFY → SYNTHESIZE
```

### Decision: Keep the review ontology

```text
Parties & Authority
Scope
Price & Payment
Term & Renewal
Risk Allocation
Confidentiality & Data
Intellectual Property
Exit
Mechanical / Integrity
```

### Decision: Keep the fresh-session execution model

```text
Worker → Artifact → Mailbox → Worker
```

### Important constraint

The ontology should define the vocabulary and coverage of review, not force every contract to receive identical weighting.

The actual review should be driven by:

```text
Base Review Domains
        +
Contract-Type-Specific Domains
        +
Freelancer Playbook
        +
Relevant Context / Jurisdiction
```

---

## 5. Current Conceptual Model

These are three separate layers:

### Review Algorithm

**How the contract is reviewed**

```text
MATCH
  ↓
EXTRACT
  ↓
ASSESS
  ↓
VERIFY
  ↓
SYNTHESIZE
```

### Review Ontology

**What the system reviews**

```text
Parties
Scope
Payment
Term
Risk
Confidentiality / Data
IP
Exit
Mechanical Integrity
```

### Execution Architecture

**How the AI work is executed**

```text
Fresh Session
   ↓
Artifact
   ↓
Mailbox
   ↓
Fresh Session
   ↓
Artifact
   ↓
...
```

---

## 6. Next Design Question

The next important problem is to define the **exact structure of the artifacts exchanged through the mailbox at each stage**.

That will determine whether the fresh-session principle provides real:

- isolation,
- traceability,
- reproducibility,
- verification,
- and reliable handoffs.

