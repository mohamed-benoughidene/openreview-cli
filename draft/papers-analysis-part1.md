# Papers Analysis — Part 1 (P-1 through P-5)

═══════════════════════════════════════════
PAPER P-1: A Few Good Clauses Comparing LLMs vs Domain-Trained SLMs.pdf.md
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"This paper evaluates whether a domain-trained Small Language Model (SLM) can outperform frontier Large Language Models on structured contract extraction while operating at dramatically lower cost."
___

METHODOLOGY
Dataset (name, size, source): 24 held-out SEC EDGAR contracts, 508 human-labelled annotations across 26 extraction targets, annotated by legal professionals with senior adjudication.
Model or approach: Olava Extract (domain-trained self-hosted legal-domain Mixture-of-Experts SLM, LoRA fine-tuned on 89,517 synthetic training labels) vs. five frontier baselines: Claude Opus 4.6, Claude Sonnet 4.6, Gemini 2.5 Pro, Gemini 3.1 Pro Preview, GPT-5.4 (all zero-shot).
Evaluation method: Macro and micro precision, recall, F1; field-level scoring by category (6 categories); per-document cost and latency measurement. No confidence intervals or significance testing.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
If no number exists, quote the exact text from the paper.
F1: Olava Extract micro F1 = 0.842, macro F1 = 0.812; strongest frontier baseline (Gemini 3.1 Pro Preview) micro F1 = 0.820, macro F1 = 0.796.
F2: Olava Extract cost per document (batched) = $0.018; frontier API costs ranged from $0.149 to $0.456 per document. Cost reduction of 78% to 97% versus frontier models.
F3: Olava Extract precision = 0.812 micro, 0.780 macro — highest of all models evaluated.
F4: Olava Extract led outright on 5/26 fields, tied for leader on 4, within 0.05 F1 of leader on 10 more, trailed by >0.05 F1 on 7.
F5: Strongest category: short-text identifiers (mean F1 = 0.975). Weakest category: currency fields (Annual Contract Value F1 = 0.333; Total Contract Value F1 = 0.700).
F6: Per-document latency: Olava Extract unbatched = 131.55 s, batched = 313.69 s (but total wall-clock for 24-contract batch = 6 min 27 s).
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "the evaluation set should be expanded to support confidence intervals, significance testing, and inter-annotator agreement, ideally stratified by contract type, length, and field prevalence."
L2: "the weakest field categories would benefit from targeted training data, normalisation-aware matching rules, and revised field-prompt design."
L3: "the benchmark should be expanded to cover a broader range of contract types, including amendments, statements of work, order forms, addenda, exhibits, and schedules."
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Contracts
Legal domain or jurisdiction if specified: U.S. (SEC EDGAR filings)
Matches target domain (contracts / legal docs)? YES
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Domain-trained SLM achieves extraction F1 of 0.842, matching/surpassing frontier LLMs on structured contract extraction.
F2 → At $0.018/doc batched, per-document cost is 8×–25× cheaper than frontier API baselines, enabling high-volume contract review.
F3 → Highest precision (0.812 micro) means fewer hallucinated extractions, reducing downstream review burden.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR  = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — LoRA fine-tuning and vLLM serving are production-grade today.
F2: READY — self-hosted GPU inference with batching is a standard deployment pattern.
F3: READY — precision advantages can be realized without additional research.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE — P-1 studies structured extraction; other papers in this set address different tasks (discrepancy detection, classification survey, agent frameworks, governance reasoning).
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Evaluation is limited to 24 contracts (508 annotations) with no confidence intervals or significance testing, though annotation by multiple lawyers with senior adjudication is rigorous.
════════════════════════════════════════════

═══════════════════════════════════════════
PAPER P-2: AgentScope 1.0 A Developer-Centric Framework for Building Agentic Applications.pdf.md
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"AgentScope introduces major improvements in a new version (1.0), towards comprehensively supporting flexible and efficient tool-based agent-environment interactions for building agentic applications."
___

METHODOLOGY
Dataset (name, size, source): N/A — framework paper with no empirical evaluation dataset.
Model or approach: ReAct-paradigm agent framework with modular foundational components (message, model, memory, tool), agent-level infrastructure (real-time steering, parallel tool calling, dynamic tool provisioning, state persistence, hooks), built-in agents (Deep Research, Browser-use, Meta Planner), multi-agent pipelines, evaluation module, Studio visual platform, and Runtime sandbox deployment.
Evaluation method: Descriptive architecture with example applications and code listings; no systematic benchmarks or comparative empirical evaluation against other frameworks.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
If no number exists, quote the exact text from the paper.
F1: Framework integrates 5 major LLM provider families (OpenAI/DashScope/Anthropic/Gemini/Ollama) with full feature support (streaming, tools, vision, reasoning).
F2: Supports both stateful and stateless MCP clients for remote tool integration.
F3: Group-wise tool management addresses the "paradox of choice" — "studies have shown that an overabundance of tools can actually degrade performance."
F4: Built-in evaluation module offers GeneralEvaluator (sequential) and RayEvaluator (distributed) for large-scale benchmark execution.
F5: Runtime provides FastAPI-based deployment with A2A protocol support and sandboxed tool execution (Filesystem, Browser, Training sandboxes).
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: No explicit limitations section is present in this framework paper. The paper describes design choices and future directions without enumerating limitations.
L2: No empirical comparison against other agent frameworks (LangChain, CrewAI, AutoGen, etc.) is provided.
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): N/A — software framework for building agentic applications
Legal domain or jurisdiction if specified: N/A
Matches target domain (contracts / legal docs)? PARTIAL — applicable as infrastructure for deploying legal AI agents
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Multi-provider LLM abstraction enables swapping models without application changes, useful for cost-optimized legal pipelines.
F2 → MCP client architecture allows legal agents to integrate with external legal databases, contract repositories, and court filing systems.
F3 → Group-wise tool management reduces prompt context consumption, relevant for long legal documents where token budgets are tight.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR  = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — available as open-source (github.com/agentscope-ai/agentscope).
F2: READY — MCP support is documented and implemented.
F3: READY — group-wise tool management is implemented.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE — framework paper; no empirical findings to conflict with other papers.
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: WEAK (as an empirical study); N/A as an architecture/design paper.
Reason (1 sentence): This is a systems/architecture paper with no quantitative evaluation, comparative benchmarks, or user studies; evidence is limited to architectural design descriptions and example applications.
════════════════════════════════════════════

═══════════════════════════════════════════
PAPER P-3: A Survey of Classification Tasks and Approaches for Legal Contracts.pdf.md
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"Given the large size and volumes of contracts and their underlying inherent complexity, manual reviews become inefficient and prone to errors, creating a clear need for automation."
___

METHODOLOGY
Dataset (name, size, source): 14 English-language contract datasets reviewed (11 public, 1 non-public, 2 proprietary) including LEDGAR (60,540 contracts, 846,274 provisions), CUAD (510 contracts, 13,101 labeled clauses), ContractNLI (607 contracts), UNFAIR-ToS (50 ToS, 12,011 clauses), and others.
Model or approach: Methodology taxonomy with three categories: Traditional Machine Learning (SVM, Naive Bayes, Random Forest with BoW/TF-IDF/word2vec features), Classical Deep Learning (MLP, BiLSTM, CNN), and Transformer-based approaches (BERT, RoBERTa, LEGAL-BERT, LLMs).
Evaluation method: Survey of best-performing results from 52 initially identified articles (22 + 30 from snowballing) across 7 classification tasks; includes evaluation techniques summary.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
If no number exists, quote the exact text from the paper.
F1: "300% increase in publications from 2016 to 2020 in the legal NLP field" — information extraction and classification accounted for 39% of the sample.
F2: LEDGAR contains 60,540 Exhibit-10 material contracts, 846,274 provisions, 12,608 distinct labels (semi-automatically annotated).
F3: CUAD contains 510 commercial contracts, 13,101 labeled clauses across 41 legal clause categories and 25 contract types.
F4: UNFAIR-ToS: 8.6% (1,032) of 12,011 clauses flagged as potentially unfair across 50 ToS documents.
F5: LEXDEMOD: 7,092 clauses from 23 lease contracts, 8,230 span annotations across 7 deontic types.
F6: Memnet-ToS: 100 ToS documents, 21,063 clauses, 11.1% (2,346) flagged as potentially unfair.
F7: RuleNN achieved AUC-PR scores 6.8×, 7.6×, and 1.5× higher than ILP, StarAI, and other neurosymbolic approaches respectively.
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "After applying these criteria, 52 articles remain... resulting in a set of 22 relevant articles... this may result in the omission of some studies" — the survey acknowledges possible omission of relevant work despite systematic methodology.
L2: "This survey focuses exclusively on English-language contracts" — excludes non-English contract classification.
L3: The survey is limited to 7 identified classification tasks and does not cover other contractual NLP tasks such as summarization, question answering, or information extraction.
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Contracts (various types: employment, lease, license, service agreements, terms of service, NDAs, software engineering contracts)
Legal domain or jurisdiction if specified: Primarily U.S. (SEC EDGAR), some EU (UNFAIR-ToS uses EU Directive 93/13), Australia (Norm dataset)
Matches target domain (contracts / legal docs)? YES
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → 7 classification tasks (topic, risky/unfair, deontic, ambiguity, norm conflict, obligatory, NLI) define the landscape of automated contract analysis product features.
F2 → LEDGAR's 12,608-label topic taxonomy provides a pre-existing schema for clause-level classification in commercial contracts.
F3 → CUAD's 41 clause types across 510 contracts offers a labelled dataset for training clause-recognition models.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR  = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — Transformer-based methods (BERT/RoBERTa/LEGAL-BERT) dominate and are production-deployable.
F2: READY — public datasets (LEDGAR, CUAD, ContractNLI) are available for training.
F3: RESEARCH — LLM prompting for contract classification is still emerging; survey notes it needs more exploration.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE — this is a survey paper; it does not present conflicting experimental results.
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Thorough systematic review with snowballing and inclusion/exclusion criteria, but scope limited to 7 classification tasks over English-language contracts only.
════════════════════════════════════════════

═══════════════════════════════════════════
PAPER P-4: Better Call CLAUSE A Discrepancy Benchmark.pdf.md
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"no benchmark exists to systematically stress-test their reliability against the nuanced, adversarial, and often subtle flaws present in real-world contracts."
___

METHODOLOGY
Dataset (name, size, source): CLAUSE benchmark — 7,500+ perturbed contracts from CUAD (510 contracts) and ContractNLI (607 contracts), yielding 23,955 validated perturbations across 10 categories (5 perturbation types × 2 contradiction dimensions: Legal and InText).
Model or approach: GPT-4o-mini, Gemini 2.0 Flash, Gemini 2.5 Flash, LLaMa 3.3 70B Instruct. Evaluation across 4 hierarchical tasks: binary detection, contradiction type classification (3-way), span detection + explanation generation (zero-shot L1 and one-shot L2).
Evaluation method: Exact label matching for Eval 1 & 2; location_alignment (ROUGE, METEOR, BERTScore), explanation_match (LLM-as-judge 0–5 scale), law_match (binary, LLM-as-judge) for Eval 3. Human validation on 25% sample (13,275 instances) by 3 NLP experts + legal expert on ~100 samples.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
If no number exists, quote the exact text from the paper.
F1: Best binary detection F1: Gemini 2.5 achieves 63%+ on CUAD, ~51.9% on NLI (Omission_Legal). Gemini 2.5 operates in high-recall (90%+), low-precision strategy.
F2: Human validation: 98.58% contradiction validation rate across 13,275 instances; inter-rater Cohen's Kappa = 0.98 (averaged across 3 expert pairs).
F3: Law match: best model (Gemini 2.5) achieves <14% accuracy on legal citation matching.
F4: Explanation quality: Clarity scores 4.0+/5 but Completeness <2.0/5 across all models — "fluent but shallow reasoning."
F5: Legal expert evaluation: Legal Plausibility = 4.83–4.89/5, Contextual Coherence = 4.43–4.56/5, Contradiction Strength = 4.49–4.54/5, Representativeness of Risk = 4.79–4.85/5.
F6: Hardest category: Omission_Legal on NLI — GPT-4o-mini 31% F1, LLaMa-3.3 9.3% F1. LLaMa-3.3 on CUAD Structural_Flaws_Legal: 6.9% F1.
F7: One-shot prompting (L2) lowers miss rate but increases extra rate (false positives) across all models.
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "Our benchmark is built using U.S. commercial contracts from the well-regarded CUAD and ContractNLI datasets. This allows for a deep and relevant analysis of model performance in this specific, high-impact area. Consequently, our findings are most directly applicable to U.S. law."
L2: "the nature of these flaws is influenced by the capabilities of the generation model (Gemini 2.0 Flash), and our validation simplifies risk into a 'YES/NO' decision."
L3: "To assess the quality of the models' legal explanations at scale, we used other LLMs as judges. An interesting finding was that different AI judges showed slight variations in their scoring."
L4: "Our experiments provide a crucial baseline for the 'out-of-the-box' reasoning capabilities of four major LLM families as of late 2025."
L5: "a rigorous validation of our dataset was conducted by 3 NLP experts who reviewed a significant 25% sample of all generated perturbations."
L6: "Our current methodology generates multiple, distinct perturbations for each source document... Real-world contracts, however, can sometimes contain multiple, interacting issues."
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Contracts (commercial: leases, joint ventures, employment, NDAs)
Legal domain or jurisdiction if specified: U.S. commercial contract law (CUAD and ContractNLI are U.S.-centric)
Matches target domain (contracts / legal docs)? YES
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Even best models achieve only 63% F1 on binary discrepancy detection — legal document review automation has significant accuracy gaps.
F2 → Law match <14% demonstrates models cannot reliably produce or match legal citations, critical for any product feature that requires referencing specific statutes.
F3 → Explanation quality: high clarity (4.0+) but low completeness (<2.0) means models produce confident-sounding but substantively shallow legal reasoning.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR  = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: RESEARCH — 63% F1 is too low for unsupervised production deployment in legal discrepancy detection.
F2: RESEARCH — <14% law citation accuracy is not production-ready for any statute-referencing feature.
F3: RESEARCH — Shallow explanations (Completeness <2.0/5) indicate models lack depth for unsupervised legal reasoning.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE — P-4 tests legal discrepancy detection (finding flaws in contracts), while P-1 tests structured extraction (pulling known fields from contracts). Different tasks, different conclusions; no direct conflict. P-4's finding that all models struggle (best F1 63%) on discrepancy detection does not contradict P-1's finding that SLMs can extract clauses at F1 84%.
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Large-scale benchmark (23,955 perturbations) with high inter-rater reliability (Cohen's Kappa = 0.98) and expert validation, but limited to U.S. contracts and AI-generated perturbations from a single generation model (Gemini 2.0 Flash).
════════════════════════════════════════════

═══════════════════════════════════════════
PAPER P-5: CHANCERY Evaluating Corporate Governance Reasoning Capabilities in Language Models.pdf.md
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"while multiple legal datasets exist, none have thus far focused specifically on reasoning tasks."
___

METHODOLOGY
Dataset (name, size, source): CHANCERY benchmark — 502 handcrafted binary classification questions based on 79 corporate charters drawn from a dataset of 10,000+ real-life corporate charters, covering 24 corporate governance principles.
Model or approach: QwQ-32B, DeepSeek-R1, Claude 3.7-Sonnet, Llama3.1-70B, GPT-4o; plus ReAct agent and CodeAct agent frameworks.
Evaluation method: Binary classification accuracy (whether proposed executive/board/shareholder action is consistent with charter). Strict prompt requiring only "Yes" or "No".
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
If no number exists, quote the exact text from the paper.
F1: GPT-4o achieves 75.2% (highest among standalone models); CodeAct agent achieves 78.1% (highest overall); ReAct agent achieves 76.1%.
F2: DeepSeek-R1 = 58.6%, Claude 3.7-Sonnet = 64.5%, QwQ-32B = 55.4%, Llama3.1-70B = 72.7%.
F3: Without strict binary prompt, GPT-4o drops to 29.1% and Llama3.1-70B drops to 22.1%.
F4: Hardest principles (DeepSeek-R1): Anti-greenmail 27.6%, Secret Ballots 33.3%, Poison Pills 41.9%.
F5: Easiest principles (DeepSeek-R1): Control-Share Cash-Out Laws 63.6%, Cumulative Voting 59.0%, Bylaw/Charter Amendment Limitations 58.1%.
F6: Multi-hop queries: 58.1% vs single-hop: 73.3%; queries needing extra search: 58.0% vs no search: 70.7%.
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "the benchmark could be expanded to increase the number and diversity of the included charters... we only use 79 charters from the 10k+ provided."
L2: "the benchmark is currently highly US-centric. All 79 charters are drawn solely from companies that are headquartered in US states."
L3: "the dataset could be expanded to encompass other forms of governance... new forms of company governance have emerged to govern industries such as the cryptocurrency and blockchain industry (under the rubric of DAO – distributed autonomous organization)."
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Corporate governance charters
Legal domain or jurisdiction if specified: U.S. corporate law (Delaware General Corporation Law)
Matches target domain (contracts / legal docs)? PARTIAL — corporate charters are legal governance documents but are not commercial contracts of the type (SaaS, procurement, employment) typically targeted by the product.
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Highest accuracy for any model is 78.1% (CodeAct agent) — corporate governance reasoning is not yet reliable enough for unsupervised deployment.
F2 → Multi-hop reasoning (58.1%) and queries needing external search (58.0%) are substantially harder — product features requiring multi-step charter analysis need explicit reasoning pipeline design.
F3 → Strict binary prompt engineering (GPT-4o: 75.2% vs 29.1%) is critical for reliable classification output.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR  = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: RESEARCH — 78% accuracy is below the threshold for unsupervised legal reasoning.
F2: RESEARCH — multi-hop reasoning at 58% shows models cannot reliably handle compound charter queries.
F3: NEAR — agentic frameworks (ReAct/CodeAct) show measurable improvement (76–78%) over standalone models (55–75%), suggesting a path to production via agent orchestration.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE — P-5 addresses a unique domain (corporate governance charter reasoning) not covered by any other paper in this set. No direct conflicts with P-1 (contract extraction), P-2 (agent framework), P-3 (classification survey), or P-4 (discrepancy detection).
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): 502 handcrafted questions with ground truth labelled by the research team offers moderate scope; limited to 79 U.S. corporate charters and no inter-annotator agreement reported for the ground-truth labels.
════════════════════════════════════════════
