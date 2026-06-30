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
# Papers Analysis — Part 2 (P-6 through P-10)

═══════════════════════════════════════════
PAPER P-6: Citation Grounding Detecting and Reducing LLM Citation Hallucinations via Legal Citation Graphs
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"Large language models systematically hallucinate legal citations – fabricating statute references, citing repealed provisions, and confusing jurisdictions – yet no automated method exists to measure or reduce this behavior at scale."

METHODOLOGY
Dataset (name, size, source):
Citation graph from 100.8 million Ukrainian court decisions (EDRSR — Unified State Register of Court Decisions), 502 million edges, 21,736 unique statute nodes. Evaluation: 100 Ukrainian legal queries across 7 domains. CG-DPO: 2,244 court decisions (1,795 training, 224 validation, 225 test pairs).

Model or approach:
Five systems evaluated: Claude Haiku 4.5, Mistral Pixtral Large, Amazon Nova Pro, Amazon Nova Lite (all via AWS Bedrock), and LEX Chat (Claude Sonnet 4 with RAG over EDRSR). For CG-DPO: Qwen2.5-7B-Instruct with LoRA (rank 16, alpha 32), DPO loss, 3 epochs, batch size 16, learning rate 2×10⁻⁵.

Evaluation method:
Citation Grounding (CG) metric — fraction of LLM-generated citations verifiable against ground-truth citation graph. Three-component decomposition: Citation Precision (CP — existence), Citation Relevance (CR — contextual appropriateness via XLM-RoBERTa embeddings), Citation Temporality (CT — temporal validity). CG-DPO evaluated by classification accuracy of preferred vs. rejected pairs.

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
F1: CG ranges from 0.791 to 0.873 across five systems, meaning 13–21% of generated legal citations are hallucinated.
F2: RAG-augmented system (LEX Chat) achieves highest CG = 0.873 at lowest citation density (2.9 per response).
F3: Constitutional law achieves CG = 1.0 across all five models universally.
F4: Family and labor law show highest inter-model variance, CG ranging from 0.46 to 0.90.
F5: Density–accuracy correlation across raw models is weak (ρ = −0.12).
F6: CG-DPO achieves 98.5% mean validation accuracy (rewards margin +14.9, std < 0.3 pp across 3 seeds), 100% training accuracy.
F7: Of 54 citations flagged as hallucinated by CG, all 54 refer to real existing statute articles — 32 (59%) are graph coverage gaps, 22 (41%) confirmed after importing missing codexes.
F8: Claude Haiku 4.5 achieves CG = 0.855 with highest citation density (4.8 per response); Amazon Nova Lite scores lowest (CG = 0.791).

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: Graph coverage — G is built exclusively from court decisions and reflects only statutes that courts actually cite. 59% of flagged hallucinations are graph coverage gaps (real articles not yet represented in judicial citation practice).
L2: Temporality implementation — current CT component checks statute existence in G, not whether a specific version was in force at date t. Full temporal-aware verification requires a versioned legislation API.
L3: Jurisdiction — all experiments are on Ukrainian law, a codified (civil law) system. Adaptation to common law systems would require modifying the graph structure (Vn becomes prior decisions rather than statute articles).
L4: CG-DPO evaluation scope — the 98.5% accuracy measures discrimination between correct and corrupted citations on held-out data. End-to-end evaluation of whether CG-DPO-trained models produce fewer hallucinations in open-ended generation requires additional techniques (SFT pre-training, larger model scales, or alternative alignment methods) and constitutes the primary direction for future work.

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Court decisions (case law / judicial decisions)
Legal domain or jurisdiction if specified: Ukrainian law (civil law / codified system)
Matches target domain (contracts / legal docs)? PARTIAL — focuses on legal citations in court decisions, not contracts specifically, but methodology applies to any legal system with structured citations.

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → A product using general LLMs for contract review should expect 13–21% hallucinated legal citations without specialized grounding.
F2 → RAG augmentation is a reliable path to improve citation accuracy while reducing citation density (2.9 vs 4.8 per response).
F3 → Constitutional/central legal provisions can be cited with perfect accuracy, while domain-specific provisions (family, labor, military) require additional verification.
F5 → Citation density alone is not a reliable proxy for accuracy; architectural decisions (RAG vs raw model) matter more than density-accuracy trade-offs.
F6 → Graph-based algorithmic preference pairs can substitute for human annotation at 98.5% accuracy for citation alignment, eliminating the need for expensive legal expert annotation.
F7 → CG is a conservative metric — it produces false positives but no false negatives, which is desirable for legal applications (better to flag a correct citation than miss a fabricated one).

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — citation graph construction and CG metric can be implemented with existing regex, SQLite, and embedding libraries (XLM-RoBERTa, PyMuPDF).
F2: READY — RAG with standard retrieval libraries (e.g., LangChain, LlamaIndex alternatives with httpx) and vector databases is implementable today.
F3: READY — domain-level accuracy monitoring is implementable with existing tooling.
F5: READY — density-accuracy analysis tools exist today.
F6: NEAR — CG-DPO requires LoRA fine-tuning infrastructure (H100 GPU, TRL library) and is implementable with existing libraries but needs 6–12 months of integration work for production deployment.
F7: READY — coverage gap analysis can be implemented today with existing database tools.

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: STRONG
Reason (1 sentence): Peer-reviewed (arXiv), extremely large dataset (502M edges from 100.8M court decisions), reproducible with open-source release of citation graph, evaluation framework, and CG-DPO dataset, with comprehensive cross-domain analysis across 5 systems.

═══════════════════════════════════════════
PAPER P-7: Computational Law Datasets, Benchmarks, and Ontologies
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"Considering these aspects, we present an up-to-date review of the literature on datasets, benchmarks, and ontologies proposed for computational law."

METHODOLOGY
Dataset (name, size, source):
This is a survey/literature review paper — no original dataset. Reviews named datasets: EURLEX57K (57K legal docs, EU), LeNER-Br (70 documents, Portuguese), RulingBR (10,623 Brazilian court decisions), VICTOR (44,855 suits, 628,820 documents), CaseHOLD (53,137 questions, Harvard Law Library), CUAD (510 contracts, 25 types, 13,101 labels), Pile of Law (256GB, 35 sources), EUR-Lex-Sum (24 languages, up to 1,500 docs/language), Multi-LexSum (40K docs, 9K summaries), CLC (250K+ cases, UK), Super-SCOTUS, MAUD (152 merger agreements, 47,457 annotations), CAIL2018 (2,676,075 criminal cases, Chinese), CAIL2019-SCM (8,964 triplets), JEC-QA (26,365 questions), LeCaRD (107 queries, 43,823 cases), LEVEN (8,116 Chinese docs, 108 event types, 150,977 mentions), CDD (30,481 Chinese cases), EQUALS (6,914 triplets), LeDQA (100 cases, 4,800 pairs), SLDS (18,175 Swiss decisions), LegalDiscourse (100,000+ state laws, US). Benchmarks: SJP (85K cases), MILDSum (3K decisions), LexGLUE (7 datasets), LBOX OPEN (147K cases), FairLex, FEDLEGAL, LegalBench (162 tasks, 20 LLMs), LegalBench-RAG, LEXTREME (11 datasets, 24 languages), LAiW, LexEval (23 tasks, 14,150 questions), ArabLegalEval, IL-TUR, COLIEE. Ontologies: FOLaw, LRI-Core, CLO, JurWordNet, LKIF core, OPJK, JuDO, PrOnto, ViLO, Legal-Onto, ELTS.

Model or approach:
N/A — survey paper, no models trained or evaluated.

Evaluation method:
N/A — survey paper, no experiments conducted.

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
F1: LegalBench consists of 162 different legal reasoning tasks evaluating 20 LLMs from 11 families.
F2: LEXTREME benchmark comprises 11 legal datasets across 24 languages.
F3: CUAD dataset cost approximately $2,000,000 to replicate (40 lawyers, year-long effort, 9,283 pages reviewed 4+ times at $500/hour).
F4: CUAD contains 510 contracts of 25 types, 13,101 labeled clauses across 41 label categories.
F5: LEVEN dataset has 8,116 Chinese legal documents annotated with 108 event types, totaling 150,977 event mentions.
F6: MAUD contains 152 public merger agreements with 47,457 annotations (8,226 deal point text + 39,231 QA).
F7: Pile of Law is 256GB from 35 sources including court filings, opinions, regulations, and contracts.

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "we observe the terms 'dataset' and 'benchmark' may be used interchangeably by the authors of the published papers" — inconsistent terminology across the literature.
L2: Regarding ontologies: "reusability of legal ontologies is still an open issue that should be improved with further studies" (quoting de Oliveira Rodrigues et al., 2019).
L3: Survey only covers English, Chinese, Portuguese, German, French, Italian, Korean, Arabic, Hindi, and Indian languages — not exhaustive coverage of all legal NLP resources globally.

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Mixed — contracts (CUAD, MAUD, ContractNLI), court decisions/case law (CLC, VICTOR, CAIL2018, Super-SCOTUS), legislation (EURLEX57K, Pile of Law), regulations, terms of service (UNFAIR-ToS), privacy policies (PrivacyQA).
Legal domain or jurisdiction if specified: Multi-jurisdictional — EU, UK, US, Brazil, China, India, Switzerland, Korea, Canada, France, Italy, Germany, Vietnam, Arab countries.
Matches target domain (contracts / legal docs)? YES — covers contract-specific datasets (CUAD, MAUD, ContractNLI, LEDGAR) and broader legal NLP resources directly relevant to contract analysis.

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → LegalBench's 162-task framework provides a comprehensive evaluation suite for assessing any new legal LLM's reasoning capabilities.
F2 → Multilingual benchmarks (LEXTREME, 24 languages) indicate demand for legal NLP beyond English-only systems.
F3 → The $2M cost of CUAD demonstrates that expert-annotated legal datasets are expensive to create, making public benchmarks critical for product development.
F4 → CUAD's 41 label categories provide a proven taxonomy for contract clause classification in product development.
F6 → MAUD's merger agreement focus (152 agreements, 47K+ annotations) provides targeted training/evaluation data for M&A contract analysis products.
F7 → Pile of Law (256GB, 35 sources) provides a large-scale, diverse corpus for pre-training or fine-tuning legal language models.

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — LegalBench is a publicly available benchmark, implementable today.
F4: READY — CUAD dataset and its annotation taxonomy are publicly available today.
F6: READY — MAUD dataset is publicly available.
F7: READY — Pile of Law is publicly available for model pre-training.

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE — this is a survey paper and does not present original experimental findings.

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Comprehensive survey covering named resources with detailed citations and taxonomy, but no original experiments, and the review's depth per resource is limited by the breadth of coverage across datasets, benchmarks, and ontologies.

═══════════════════════════════════════════
PAPER P-8: GRAPH-GRPO-LEX Contract Graph Modeling and Reinforcement Learning with Group Relative Policy Optimization
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"This work aims to simplify and automate the task of contract review and analysis using a novel framework for transforming legal contracts into structured semantic graphs, enabling computational analysis and data-driven insights."

METHODOLOGY
Dataset (name, size, source):
43 contracts from CUAD contract collection (Distribution & Channel Sales family), containing approximately 1,600 clauses. Semi-automated labeling with LLM annotation validated via alt-test. Annotation targets 4 node types (CLAUSE, PARTY, DEFINED_TERM, VALUE) and 6 edge types (IS_PART_OF, REFERENCES, USES, MENTIONS_PARTY, DEFINES, CONTAINS).

Model or approach:
Meta-Llama-3.1-8B-Instruct with QLoRA (rank=8, lora_alpha=16, lora_dropout=0.05). Two-stage: (1) Supervised Fine-Tuning (SFT) baseline, (2) GRPO reinforcement learning with gated reward function. GRPO hyperparameters: learning rate 2e-6, group size 4 generations per prompt, temperature 0.3-0.4, top-p 0.9, repetition penalty 1.2. Single NVIDIA A100 GPU (80GB VRAM).

Evaluation method:
Strict and fuzzy micro-precision, recall, F1. Reward function combining: structure score (valid JSON), strict/fuzzy F1 scores, embedding similarity (semantic score), graph edit distance. Alt-test (Benjamini-Yekutieli FDR, q=0.05) to validate LLM labels as human-annotation substitute.

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
F1: Alt-test results: ω = 0.99 (all annotators exceeded after FDR), Average Advantage Probability = 0.907 — statistically significant justification for using LLM labels instead of human annotators.
F2: SFT baseline — strict_micro_f1 = 0.6612 (eval), fuzzy_micro_f1 = 0.6929 (eval), invalid_json_rate = 0.0.
F3: GRPO (gated) — strict_micro_precision = 0.806, strict_micro_recall = 0.790, strict_micro_f1 = 0.798, fuzzy_micro_precision = 0.817, fuzzy_micro_recall = 0.802, fuzzy_micro_f1 = 0.809, invalid_json_rate = 0.02.
F4: Gated GRPO achieves 6× better F1 scores compared to non-gated GRPO approach.
F5: Zogenix Inc. case study: 257 nodes, 916 edges, graph density = 0.014, dependency depth = 6, 131 orphans, 97 leaves, orphan ratio ≈ 0.5, leaf ratio = 0.377, 11 articulation points.
F6: Dataset contained ~1,600 clauses across 43 contracts in the Distribution & Channel Sales family.
F7: SFT train strict_micro_f1 = 0.6547, eval strict_micro_f1 = 0.6612.

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: Computational cost — "While GRPO does not require a large dataset, it relies on additional sampling at an increased computational cost." Experiments limited group size to 4 on single A100.
L2: Non-gated GRPO produced "very modest results which did not improve on our SFT training" — the compound reward function was too noisy when all signals were applied simultaneously.
L3: High-temperature sampling (0.6-0.7) severely impacted ability to generate valid JSON structured responses, requiring temperature reduction to 0.3.
L4: Base tokenizer produced "gibberish, other languages and symbols" requiring ASCII clamp as LogitsProcessor.

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Contracts — specifically Distribution & Channel Sales family from CUAD collection.
Legal domain or jurisdiction if specified: General commercial contracts (US jurisdiction implied via CUAD dataset source).
Matches target domain (contracts / legal docs)? YES — entirely focused on contracts.

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → LLM labels can substitute for human annotation in contract graph extraction with statistical confidence (ω = 0.99), dramatically reducing annotation cost.
F2 → SFT alone achieves reasonable baseline (strict_f1 = 0.661) for node/edge extraction from clauses.
F3 → GRPO improves SFT by ~21% relative in strict F1 (0.661 → 0.798), demonstrating reinforcement learning value for contract graph construction.
F4 → Gated (staged) reward signals are essential for effective GRPO training — all-at-once reward functions fail.
F5 → Contract graph metrics (density, depth, articulation points, orphan ratio) provide quantifiable risk indicators directly usable in a "contract linter" product.
F6 → The 1,600-clause dataset with node/edge annotations is a reproducible training resource for contract graph modeling.

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — alt-test methodology and LLM-based annotation are implementable today with existing libraries.
F2: READY — SFT on Llama-3.1-8B with QLoRA is implementable with existing TRL/HuggingFace libraries.
F3: NEAR — GRPO training requires A100 (80GB) GPU and careful reward function engineering; production deployment needs 6–12 months.
F4: NEAR — gated GRPO approach is novel and requires further engineering for stable production use.
F5: READY — graph metrics computation (networkx, igraph) and contract linter logic are implementable today.
F6: READY — dataset construction from CUAD contracts is reproducible with existing tools.

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Solid experimental design with SFT baseline comparison and gated GRPO innovation, but limited to 43 contracts (1,600 clauses) in a single contract family, single model (Llama-3.1-8B), and no human evaluation of downstream contract review quality.

═══════════════════════════════════════════
PAPER P-9: LegalBench-RAG A Benchmark for Retrieval-Augmented Generation in the Legal Domain
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"Existing benchmarks, such as LegalBench, assess the generative capabilities of Large Language Models (LLMs) in the legal domain, but there is a critical gap in evaluating the retrieval component of RAG systems. To address this, we introduce LegalBench-RAG, the first benchmark specifically designed to evaluate the retrieval step of RAG pipelines within the legal space."

METHODOLOGY
Dataset (name, size, source):
LegalBench-RAG: 6,858 (6,889) query-answer pairs over 714 documents, corpus of 79,704,214 characters (~80M). Derived from 4 source datasets: ContractNLI (95 docs, 977 queries), CUAD (462 docs, 4,042 queries), MAUD (150 docs, 1,676 queries), PrivacyQA (7 docs, 194 queries). All human-annotated by legal experts. Also LegalBench-RAG-mini: 776 queries, 72 documents, 8,682,104 characters.

Model or approach:
Benchmark only — experiments use OpenAI text-embedding-3-large, SQLite Vec vector database, Cohere rerank-english-v3.0 reranker. Two chunking strategies: naive fixed-size (500 chars, no overlap) and Recursive Character Text Splitter (RCTS). Two post-processing: no reranker vs. Cohere Reranker.

Evaluation method:
Precision@k and Recall@k (k = 1, 2, 4, 8, 16, 32, 64). Results weighted equally per dataset (not by document or query count). Metrics evaluate retrieval only, not generation.

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
F1: Best overall configuration: RCTS + no reranker. PrivacyQA achieves highest Precision@1 = 14.38% and Recall@64 = 84.19%.
F2: MAUD is the most challenging dataset: Precision@1 = 2.65% (best config), Recall@64 = 28.28%.
F3: Cohere Reranker underperformed compared to no reranker across all datasets and configurations.
F4: For RCTS + No Reranker across ALL datasets: Precision@1 = 6.41%, Precision@64 = 1.45%, Recall@1 = 4.94%, Recall@64 = 62.22%.
F5: For Naive + No Reranker across ALL: Precision@1 = 2.40%, Recall@64 = 76.39%.
F6: ContractNLI with Naive + No Reranker achieves best Precision@1 = 16.45%.
F7: Total corpus: 714 documents, 79.7M characters, with average document length = 443,242 characters (dominated by MAUD at 351,476 avg).
F8: CUAD dataset creation estimated at ~$2,000,000 to replicate (40+ lawyers, 9,283 pages, $500/hour).

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "This dataset is not made of an exhaustive list of all existing documents in the legal industry. For example, this benchmark does not assess structured numerical data parsing, which is relevant for cases involving financial fraud. It also does not assess the parsing and analyzing of medical records, which is relevant in personal injury suits."
L2: "Notably, the queries in this benchmark are always answered by exactly one document, so this benchmark does not assess the ability of a retrieval system to reason across information found in multiple documents."
L3: "there is room to create even more complex queries that require a very high number of hops to generate the correct snippets."
L4: "The observed low precision values could be due to the highly targeted and concise nature of the ground truth."

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Contracts (NDAs, M&A agreements, commercial contracts) and privacy policies.
Legal domain or jurisdiction if specified: General commercial/consumer law — ContractNLI (NDAs), CUAD (private contracts), MAUD (M&A of public companies), PrivacyQA (consumer app privacy policies).
Matches target domain (contracts / legal docs)? YES — 3 of 4 source datasets are contracts, and the benchmark is specifically designed for legal retrieval evaluation.

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → RCTS chunking without domain-specific reranker is the most effective retrieval strategy for legal document RAG.
F2 → M&A agreements (MAUD) are significantly harder to retrieve from than other contract types, requiring specialized retrieval approaches.
F3 → General-purpose rerankers (Cohere) degrade retrieval performance on legal text — domain-specific reranker needed.
F4 → Even best legal RAG retrieval achieves only 6.41% Precision@1 and 62.22% Recall@64, indicating significant room for improvement.
F6 → ContractNLI-style NDA retrieval achieves highest precision (16.45% @1), suggesting shorter, more structured contracts are easier to retrieve from.
F8 → The $2M estimated cost of CUAD reproduction underscores the value of public legal retrieval benchmarks for product development.

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — RCTS chunking is available in LangChain and other libraries today.
F2: READY — MAUD-based retrieval evaluation is implementable today with existing embedding models.
F3: NEAR — domain-specific rerankers for legal text are not yet production-ready and need development.
F4: READY — standard retrieval evaluation with Precision/Recall at k is implementable today.
F6: READY — NDA retrieval evaluation is implementable today.
F7: READY — the full LegalBench-RAG dataset is publicly available and immediately usable.

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: STRONG
Reason (1 sentence): First dedicated retrieval benchmark for legal RAG, with 6,858 expert-annotated QA pairs across 714 documents (80M chars), reproducible with publicly available dataset and code, though experiments limited to two chunking strategies and one reranker.

═══════════════════════════════════════════
PAPER P-10: LLMs for Law Evaluating Legal-Specific LLMs on Contract Understanding
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"How do legal-specific LLMs perform compared to general-purpose LLMs on nuanced legal tasks like contract understanding?"

METHODOLOGY
Dataset (name, size, source):
Three datasets: (1) UNFAIR-ToS — 5,532 train / 2,275 dev / 1,607 test instances, 9 classes, multi-label classification, Terms of Service contracts. (2) LEDGAR — 60,000 / 10,000 / 10,000, 100 classes, multi-class classification, Exhibit-10 material contracts from SEC EDGAR. (3) LEXDEMOD — 4,282 / 330 / 1,777, 7 classes, multi-label classification, lease contracts from LEDGAR.

Model or approach:
10 legal-specific LLMs: Legal-BERT (110M), Contracts-BERT (110M), Legal-RoBERTa (125M), CaseLaw-BERT (110M), PoL-BERT (340M), InLegalBERT (110M), InCaseLawBERT (110M), CustomInLawBERT (110M), LexLM (124M), Legal-XLM-R (184M), LexT5 (220M, exploratory). 7 general-purpose LLMs: BERT (110M), RoBERTa-base (125M), RoBERTa-large (355M), DeBERTa (149M), Longformer (127M), BigBird, GPT-3.5-Turbo (zero/few-shot). Supervised fine-tuning with learning rate 3e-5 (base models), 1e-5 (large models), batch size 8, up to 20 epochs, early stopping patience 3, max seq length 128 (UNFAIR-ToS, LEDGAR) or 256 (LEXDEMOD). Single NVIDIA V100 GPU.

Evaluation method:
Micro-F1 (μ-F1) and Macro-F1 (m-F1). Each model trained 5 times with different random seeds; best seed reported (UNFAIR-ToS, LEDGAR) or average of 3 best seeds (LEXDEMOD). Aggregated arithmetic mean ± std across tasks.

KEY FINDINGS
Specific values only — percentages, thresholds, counts.
F1: Legal-BERT (110M) achieves new SOTA on UNFAIR-ToS (μ-F1 = 96.0, m-F1 = 82.2) and LEXDEMOD (μ-F1 = 81.23, m-F1 = 78.01), outperforming RoBERTa-large (355M) despite having 69% fewer parameters.
F2: Contracts-BERT (110M) achieves new SOTA on UNFAIR-ToS (μ-F1 = 96.2, m-F1 = 83.4).
F3: Legal-specific base models outperform general-purpose base models on all tasks — e.g., Legal-BERT μ-F1 = 88.48 vs BERT base (not reported as aggregate but consistent across individual tasks).
F4: Legal-BERT, Contracts-BERT, CaseLaw-BERT, and LexLM identified as the four strong baseline models for contract understanding.
F5: RoBERTa-large remains best on LEDGAR (μ-F1 = 88.6, m-F1 = 83.6), but Legal-BERT achieves equivalent performance to general-purpose base variants on this task.
F6: PoL-BERT (340M, Pile-of-Law pre-trained) shows poor performance — μ-F1 = 73.98 ± 23.34, m-F1 = 57.58 ± 29.58, with particular failure on LEXDEMOD (μ-F1 = 41.35, m-F1 = 15.75).
F7: Legal-BERT and Contracts-BERT, pre-trained on only 354K and 76K legal documents respectively, outperform many recent legal-specific models pre-trained on millions of documents.
F8: GPT-3.5-Turbo zero-shot (μ-F1 = 41.4, m-F1 = 22.2 on UNFAIR-ToS) vs few-shot (μ-F1 = 64.7, m-F1 = 32.5) — far below fine-tuned models.

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "The limited availability of contract benchmark datasets in languages other than English poses a challenge for multilingual extension. Consequently, this study focuses solely on English-language contract tasks, leaving evaluation on non-English data for future work."
L2: "While encoder-decoder models like LexT5 and decoder-based legal-specific LLMs such as AdaptLLM and SaulLM-7B are emerging, they remain scarce. We therefore defer their benchmarking until more models become available, ensuring fair comparisons."
L3: "Additionally, this work concentrates on the nuances of contract language and does not assess performance on other legal text types, such as statutes, court decisions, or legal opinions."
L4: "A key limitation of recent legal-specific LLMs is that they are pre-trained on few, or no, diverse contract documents compared to other legal texts like legislation and court cases."
L5: Many LEDGAR paragraphs exceed the BERT 512-token context window, requiring truncation.

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Contracts — Terms of Service (UNFAIR-ToS), Exhibit-10 SEC material contracts (LEDGAR), lease contracts (LEXDEMOD).
Legal domain or jurisdiction if specified: EU consumer law (UNFAIR-ToS — European consumer protection), US SEC regulations (LEDGAR), general contract law (LEXDEMOD — lease agreements).
Matches target domain (contracts / legal docs)? YES — entirely focused on contract understanding tasks.

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Legal-BERT at 110M parameters is sufficient for contract classification SOTAs — smaller models mean lower cost and faster inference for product deployment.
F2 → Contracts-BERT (pre-trained on US contracts only) achieves the highest score on UNFAIR-ToS despite not being pre-trained on EU consumer contract data — suggesting contract language generalizes across domains.
F3 → Domain-specific pre-training consistently outperforms general pre-training for contract tasks, even with dramatically fewer parameters.
F4 → Four recommended baseline models (Legal-BERT, Contracts-BERT, CaseLaw-BERT, LexLM) provide a proven starting point for any contract classification product.
F6 → PoL-BERT (pre-trained on diverse legal texts but few contracts) performs poorly on contract tasks — general legal pre-training is not a substitute for contract-specific pre-training.
F7 → Data quality (targeted contract pre-training) matters more than data quantity for contract understanding models.
F8 → Fine-tuning (even on small models) dramatically outperforms zero/few-shot prompting with GPT-3.5-Turbo for contract classification.

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — Legal-BERT and Contracts-BERT are available on HuggingFace and fine-tunable with standard libraries today.
F2: READY — fine-tuning pipeline is implementable today with HuggingFace Transformers.
F3: READY — domain-specific model selection is a configuration decision implementable today.
F4: READY — all four recommended baselines are publicly available on HuggingFace.
F6: READY — model pre-training data analysis is implementable today.
F7: READY — data quality analysis for contract pre-training is implementable today.
F8: READY — fine-tuning pipeline comparison with prompting is implementable today.

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: STRONG
Reason (1 sentence): Comprehensive evaluation of 10 legal-specific and 7 general-purpose LLMs across 3 diverse contract datasets, with multiple seeds for statistical reliability, reproducible configuration, and publicly available models and datasets.

═══════════════════════════════════════════
═══════════════════════════════════════════
PAPER P-11: Mina A Multilingual LLM-Powered Legal Assistant Agent for Bangladesh for Empowering Access to Justice
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"Bangladesh's low-income population faces major barriers to affordable legal advice due to complex legal language, procedural opacity, and high costs." / "To address this, we developed MINA, a multilingual LLM-based legal assistant tailored for the Bangladeshi context."
___

METHODOLOGY
Dataset (name, size, source): 595 Acts comprising 18,023 Sections from the official Bangladesh Law and Justice website (as of April 2025).
Model or approach: Two-stage RAG (Act-level then Section-level retrieval) using Cohere embed-multilingual-light-v3.0 over Chroma vector stores; multi-agent architecture (Orchestrator Agent + RAG Agent) running on a LangGraph state machine; proprietary models (GPT-4o, Gemini-2.0/2.5-Flash) and open-source (Llama3.2/3.1, Gemma-3, Qwen3, Command-A) evaluated.
Evaluation method: Bangladesh Bar Council Exams 2022 and 2023 — MCQ (5-run averages, OMR-style marking), Written (human assessment by law faculty, ≥2 judges per answer, IRAC rubric), Viva Voce (chat-based oral exam, 5-evaluator averages). Benchmarked against actual candidate pass statistics.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts. If no number exists, quote the exact text from the paper.
F1: MINA scored 75–80% across all three exam stages (MCQ, Written, Viva), matching or exceeding average human performance.
F2: Operating at 0.12–0.61% of typical legal consultation costs in Bangladesh (2,000–10,000 BDT), yielding a 99.4–99.9% cost reduction relative to human-provided services.
F3: Gemini-2.5-Flash achieved best proprietary results: 77.0% (MCQ 2022 Tools), 81.8% (Written 2023 Tools), 81.0% (Viva Tools).
F4: Qwen3-30B-A3B-Instruct-2507 achieved best open-source results: 72.4% (MCQ 2023 Tools), 79.4% (Written 2023 Tools), 79.4% (Viva Tools).
F5: Human MCQ pass rates: 25.86% (10,527/40,696) in 2022; 17.96% (6,229/34,682) in 2023.
F6: Human Written pass rates: 53.94% (5,533/10,527) in 2022; 44.21% (2,754/6,229) in 2023.
F7: Two-step RAG outperformed naive RAG by 8–15 percentage points across nearly all model/setup combinations.
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "Retrieval quality is highly dependent on the underlying corpus; noisy or misaligned documents can still mislead even robust pipelines."
L2: "Although strategies like Two Step RAG improve performance, they introduce additional latency and complexity that may not scale well in real-time systems."
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Statutes (Acts and Sections) of Bangladeshi law.
Legal domain or jurisdiction if specified: Bangladesh (Bengali and English).
Matches target domain (contracts / legal docs)? PARTIAL — statutes rather than contracts; legal domain but not specifically contract analysis.
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → RAG-based legal QA can achieve bar-exam-level accuracy (75–80%) suitable for non-expert user assistance.
F2 → AI-driven legal assistance can be deployed at 99.4%+ cost reduction vs. human lawyers, enabling access-to-justice at scale.
F3 → Two-stage hierarchical retrieval (Act→Section) substantially outperforms flat naive RAG; product should implement multi-level retrieval.
F4 → Open-source models (Qwen3-30B) with RAG approach proprietary performance, enabling on-premise deployment.
F5 → Custom legal dictionary for archaic/colonial-era terminology is critical in multilingual non-Western jurisdictions.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: READY — RAG + multi-agent orchestration patterns are well-established (LangChain, Chroma, etc.).
F2: READY — cost reduction is a property of model choice and deployment architecture, not a research problem.
F3: READY — two-stage retrieval with vector DBs is implementable today.
F4: READY — Qwen3-30B and similar models are available and runnable on commodity hardware.
F5: READY — multilingual embeddings (Cohere, OpenAI) and custom dictionaries are available now.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Real bar exam evaluation with law faculty judges is rigorous, but single jurisdiction (Bangladesh) and single exam format limit generalizability.
════════════════════════════════════════════


═══════════════════════════════════════════
PAPER P-12: Natural Language Processing for the Legal Domain A Survey of Tasks, Datasets, Models, and Challenges
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"This survey explores the current landscape of NLP applications within the legal domain. It discusses its potential benefits and the practical challenges it poses."
___

METHODOLOGY
Dataset (name, size, source): 154 studies initially identified from Google Scholar and IEEE Xplore; 131 after manual filtering following the PRISMA framework.
Model or approach: Systematic literature review covering Legal Question Answering, Legal Judgement Prediction, Legal Text Classification, Legal Document Summarisation, Legal Named Entity Recognition, Legal Argument Mining, legal corpora, and legal Language Models.
Evaluation method: N/A — survey paper; synthesis across 131 selected studies with date ranges per task (LQA: 2020-2024, LJP: 2017-2024, LTC: 2018-2023, LDS: 2016-2024, NER: 2010-2022, LAM: 2009-2024, corpora: 2021-2024, LMs: 2020-2024).
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts. If no number exists, quote the exact text from the paper.
F1: "GPT-4 was reported to have passed the Uniform Bar Exam near the 90th percentile" but "Martinez suggests that its actual performance may be considerably lower, possibly around the 48th percentile overall and 15th percentile on essays."
F2: "LLMs hallucinate legal content at high rates—up to 58% in some cases."
F3: "smaller fine-tuned models still outperform [ChatGPT] by about 30 percentage points" on certain legal classification tasks.
F4: "about half of all lawyers believe LLMs will transform legal practice, with 92% anticipating at least some impact."
F5: "77% of respondents foresee efficiency gains for legal professionals and 63% predict changes in how law is taught and studied."
F6: Sixteen open research challenges identified including bias detection/mitigation, robust and interpretable models, and explainability.
F7: MultiLegalPile: "the largest open-source multilingual legal corpus available, totalling 689 GB and spanning 17 jurisdictions across 24 languages."
F8: Pile of Law: "256 GB dataset of open-source English-language legal and administrative data."
F9: LEXTREME benchmark: "11 human-annotated datasets spanning 24 languages and multiple legal domains."
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: N/A (survey paper — limitations of individual studies are catalogued, but the survey itself does not claim primary limitations). The date ranges per task may exclude very recent work (e.g., NER to 2022, LQA to 2024).
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): All types — contracts (CUAD, MAUD, LEDGAR, ContractNLI), case law (ECHR, FSCS, SCOTUS), statutes (EURLEX), regulations (CFR), privacy policies (PrivacyQA), terms of service (UNFAIR-ToS).
Legal domain or jurisdiction if specified: Multi-jurisdiction — US (SCOTUS, CaseHOLD, CUAD, MAUD), EU (ECHR, EURLEX, CJEU), Switzerland (FSCS), China (CAIL, JEC-QA), Germany, Romania, Greece, and 24 languages in LEXTREME.
Matches target domain (contracts / legal docs)? YES — covers contract-specific datasets (CUAD, MAUD, LEDGAR, ContractNLI) extensively.
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Hallucination rates up to 58% mean any legal AI product must implement verification layers (RAG grounding, citation checking) before user-facing deployment.
F2 → Fine-tuned domain models outperform general LLMs by ~30pp on classification — product should invest in domain-specific fine-tuning, not rely solely on general-purpose models.
F3 → 92% lawyer expectation of LLM impact indicates strong market readiness and user acceptance for legal AI tools.
F4 → MultiLegalPile (689 GB, 24 languages) and Pile of Law (256 GB) provide training corpora for domain-adapted models without requiring proprietary data collection.
F5 → 16 open challenges (bias, explainability, interpretability) mean products must address these from day one for regulatory and professional acceptance.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: RESEARCH — hallucination mitigation at 58% rates is an active research area, not solved.
F2: READY — fine-tuning Legal-BERT or similar on contract corpora is established practice.
F3: NEAR — market readiness is high but product reliability infrastructure (verification, red teaming) needs maturation.
F4: READY — large legal corpora are publicly available and usable for training.
F5: RESEARCH — bias detection and explainability in legal AI remain open research challenges.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE (survey synthesizing the field; individual findings are attributed to specific studies, not presented as the survey authors' own claims).
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: STRONG
Reason (1 sentence): Systematic PRISMA review of 131 studies published in ACM Computing Surveys (peer-reviewed), with reproducible search methodology and comprehensive coverage across tasks, languages, and jurisdictions.
════════════════════════════════════════════


═══════════════════════════════════════════
PAPER P-13: PAKTON A Multi-Agent Framework for Question Answering in Long Legal Agreements
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"Contract review is a complex and time-intensive task that typically demands specialized legal expertise, rendering it largely inaccessible to non-experts. Moreover, legal interpretation is rarely straightforward—ambiguity is pervasive, and judgments often hinge on subjective assessments."
___

METHODOLOGY
Dataset (name, size, source): ContractNLI (document-level NLI for contracts); LegalBench-RAG (PrivacyQA, MAUD, CUAD — NDAs, M&A agreements, commercial contracts, privacy policies).
Model or approach: Tri-agent framework — Archivist (document parsing, hierarchical tree representation, contextualized chunking), Interrogator (iterative multi-step reasoning, progressive report refinement), Researcher (hybrid retrieval: BM25 + dense embeddings + LightRAG, cross-encoder reranking). Backbone LLMs: Mistral, Qwen, Gemma, Llama, Claude, GPT-4o, DeepSeek.
Evaluation method: ContractNLI classification accuracy + per-class F1 (entailment/contradiction/neutral); LegalBench-RAG Precision@k and Recall@k; human study (60 participants, 9 criteria, 15 questions curated by 5 attorneys + Supreme Court Justice); G-EVAL LLM-as-a-Judge.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts. If no number exists, quote the exact text from the paper.
F1: PAKTON with Qwen 2.5 72B achieves F1[W] of 81.88% on ContractNLI (vs 76.99% zero-shot, 72.41% few-shot).
F2: PAKTON with Gemma 3 27B achieves F1[W] of 82.83% (vs 78.60% zero-shot).
F3: PAKTON achieves Recall@1 of 53.14% on ContractNLI (strongest baseline: 11.32% — nearly 5x improvement).
F4: PAKTON achieves Recall@1 of 23.99% on MAUD (vs 2.54% baseline), 19.94% on PrivacyQA (vs 14.38% baseline), 16.52% on CUAD (vs 12.60% baseline).
F5: Coefficient of variation in F1[W] across models: 5.7% with PAKTON vs >16% for zero-shot — variability reduced to less than one third.
F6: Performance gap between high- and low-ZS models compressed from 22.83% percentage points to 3.8% with PAKTON.
F7: Human study: PAKTON favored over GPT-4o on 8 out of 9 evaluation criteria.
F8: G-EVAL: PAKTON surpasses GPT-4o on 8 out of 9 dimensions; sole exception is "Contextual and Legal Understanding" because PAKTON acknowledges knowledge gaps under uncertainty.
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "Our system has been tested only on English-language contracts. As legal language varies significantly across languages and cultures, additional adaptation and evaluation would be necessary for multilingual or cross-lingual applications."
L2: "PAKTON has been evaluated on a subset of contract types and does not currently cover the full diversity of legal documents. Similarly, the system has not been tested across different legal jurisdictions."
L3: "Response times may be longer compared to general-purpose language models, particularly due to the iterative communication between agents. This design also increases computational cost, making it less suitable for low-latency or resource-constrained environments."
L4: "This emphasis on explainability can sometimes result in longer or less concise responses. In prioritizing clarity and justification, the system may occasionally sacrifice brevity or even slightly reduce precision."
L5: "The system's structural parsing component is optimized for standard contract formats... When documents deviate significantly from these conventions or lack a clearly defined structure, the benefits of structural parsing are reduced."
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Legal contracts — NDAs, M&A agreements, commercial contracts, consumer-facing privacy policies.
Legal domain or jurisdiction if specified: English-language contracts, US-centric legal norms.
Matches target domain (contracts / legal docs)? YES — directly targets contract analysis and question answering.
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Multi-agent architecture with hierarchical document parsing and hybrid retrieval substantially outperforms single-model and naive-RAG baselines on contract QA.
F2 → PAKTON compresses model performance variability (CV 5.7% vs >16%) — enables use of smaller, cheaper, open-source models with consistent results.
F3 → Hybrid retrieval (BM25 + dense + LightRAG graph retrieval) + cross-encoder reranking is essential; naive chunking fails (Recall@1 11.32% vs 53.14%).
F4 → Human evaluators prefer explained, grounded responses over GPT-4o — product should prioritize transparency and evidence citation over brevity.
F5 → Iterative Interrogator-style multi-step refinement (query decomposition, gap identification, progressive report drafting) measurably improves completeness.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: NEAR — multi-agent frameworks exist (LangGraph, AutoGen) but production-hardened orchestration for legal domain is not commodity.
F2: NEAR — model compression via orchestration is conceptually sound but integration work remains.
F3: READY — hybrid retrieval + reranking is well-established in IR (Haystack, LangChain, Cohere rerank).
F4: READY — explainability-focused response formatting is a prompt engineering and UI design task.
F5: NEAR — iterative multi-step reasoning with gap identification requires careful prompt engineering and latency management.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE — PAKTON's finding that multi-agent RAG without fine-tuning outperforms domain-fine-tuned models (Saul) is complementary to P-12's finding that fine-tuned models outperform general LLMs. Different mechanism (orchestration vs. fine-tuning) achieving gains.
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: STRONG
Reason (1 sentence): Multi-method evaluation (quantitative benchmarks, human study with 60 participants + legal experts, G-EVAL, statistical tests including ANOVA and regression), open-source code, and reproducibility across multiple LLM backbones.
════════════════════════════════════════════


═══════════════════════════════════════════
PAPER P-14: RCBSF A Multi-Agent Framework for Automated Contract Revision via Stackelberg Game
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"Despite the widespread adoption of Large Language Models (LLMs) in Legal AI, their utility for automated contract revision remains impeded by hallucinated safety and a lack of rigorous behavioral constraints."
___

METHODOLOGY
Dataset (name, size, source): Unified legal revision benchmark from four datasets: PrivacyQA, ContractNLI, MAUD, CUAD (privacy policies, NDAs, merger agreements).
Model or approach: RCBSF — Global Prescriptive Agent (GPA / Leader) + Constrained Revision Agent (CRA / Follower Drafter) + Local Verification Agent (LVA / Follower Auditor). Bilevel Stackelberg game optimization with 5-dimensional risk constraints (Category, Location, Evidence, Issue, Suggestion). Backbone: Qwen2.5-7B-Chat.
Evaluation method: Risk Resolution Rate (RRR — % of ground-truth risks mitigated, judged by GPT-5 evaluator), Contract Quality (CQ — 0-100 scale measuring clarity, rigor, balance, professionalism), Token Efficiency Score (TES — risks resolved per 1,000 tokens), ablation studies, sensitivity analysis.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts. If no number exists, quote the exact text from the paper.
F1: RCBSF achieves average RRR of 84.21% (vs 79.56% Iterative Refinement, 77.25% RAG, 73.26% CoT, 70.81% Standard).
F2: Average TES of 87.29% (vs 83.40% Iteration, 81.73% RAG, 76.28% CoT, 74.31% Standard).
F3: Average CQ of 86.87 (vs 79.76 Iteration, 79.81 RAG, 75.67 CoT, 73.45 Standard).
F4: Removing 5-dimensional risk constraints drops RRR by 11.06% and Win Rate to 15.2%.
F5: Removing budget penalty (lambda=0) marginally increases RRR (+0.64%) but drops TES by 12.14%.
F6: Single-iteration (K=1) reduces RRR by 7.76%; K=3 identified as Pareto-optimal stopping point.
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "The contract clauses in our unified benchmark are predominantly derived from publicly available authoritative datasets (e.g., MAUD, ContractNLI, CUAD). These clauses are structurally consistent and rarely involve highly complex cross-clause conflicts or niche scenario disputes."
L2: "Another limitation lies in the jurisdictional and linguistic bias of our validation. The datasets used for validation are predominantly sourced from United States and Common Law jurisdictions and are entirely in English."
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Legal contracts — privacy policies, non-disclosure agreements, merger agreements.
Legal domain or jurisdiction if specified: United States and Common Law jurisdictions; English only.
Matches target domain (contracts / legal docs)? YES — directly targets automated contract revision.
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Game-theoretic revision (Leader-Follower Stackelberg) improves risk resolution over iterative refinement for contract revision tasks.
F2 → Token efficiency via budget-aware optimization (87.29% TES) makes this practical for real deployments with cost constraints.
F3 → 5-dimensional structured risk constraints (Category, Location, Evidence, Issue, Suggestion) are critical; ablation shows -11% RRR without them.
F4 → GPA's explicit structured hints (e.g., "Add within 48 hours at Clause 3.1") prevent hallucinated fixes that claim resolution without changing text.
F5 → Budget penalty forces prioritization of critical/major risks over stylistic edits, balancing rigor and conciseness.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: RESEARCH — Stackelberg game formulation for text generation is novel and not widely deployed; theoretical convergence proofs are domain-specific.
F2: NEAR — token budget optimization via constrained prompting is implementable with existing LLMs.
F3: READY — structured risk taxonomy is a data engineering/prompt design task, deployable today.
F4: READY — structured hint injection into revision workflow is prompt engineering.
F5: READY — budget-aware priority weighting is a straightforward scoring mechanism.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Strong ablation study and theoretical guarantees, but single backbone LLM (Qwen2.5-7B-Chat) and benchmark clauses noted by authors as structurally consistent limit generalizability.
════════════════════════════════════════════


═══════════════════════════════════════════
PAPER P-15: SOLAR On Verifiable Legal Reasoning
───────────────────────────────────────────

PROBLEM STATEMENT
Core research question verbatim (≤2 sentences, exact quote):
"This paper investigates whether structured ontological representations can meaningfully improve legal reasoning performance for foundational models."
___

METHODOLOGY
Dataset (name, size, source): SARA (Statutory Reasoning Assessment) numeric dataset from LegalBench — 96 tax liability calculation cases based on U.S. federal tax statutes.
Model or approach: SOLAR framework — two-stage: (1) Knowledge acquisition: multi-agent (concept extraction, rule formulation, integration, validation, code generation) constructs TBox ontology + Python TBox interpreter from statutes; (2) Knowledge application: query analysis/ABox construction agent, symbolic inference via SMT solver (NLTK), answer generation agent. Backbone LLMs: GPT-4.1, GPT-4.1-mini, o4-mini, Claude 3.7 Sonnet, Gemini 2.0/2.5 Flash, Llama 3.3/4, DeepSeek V3, Qwen 2.5.
Evaluation method: Accuracy at 10% tolerance threshold (LegalBench standard), compared against zero-shot and Chain-of-Code baselines.
___

KEY FINDINGS
Specific values only — percentages, thresholds, counts. If no number exists, quote the exact text from the paper.
F1: Foundational (non-reasoning) models with SOLAR achieve 76.4% average accuracy vs 18.8% zero-shot — a 57.6 percentage point improvement.
F2: Performance gap between reasoning and non-reasoning models reduced from 68.2 percentage points (87.0% vs 18.8% zero-shot) to 5.9 percentage points (82.3% vs 76.4% with SOLAR).
F3: SOLAR uses ~4,000 tokens per query vs ~8,000 for zero-shot (45% reduction) and ~8,500 for Chain-of-Code (48% reduction).
F4: DeepSeek-V3 improved from 15.6% (zero-shot) to 82.3% (SOLAR); Gemini-2.0-Flash improved from 6.2% to 64.6%.
F5: GPT-4.1-mini improved from 21.9% (zero-shot) to 86.5% (SOLAR).
F6: Standard deviation reduced to 0.08 (SOLAR) vs 0.28 (zero-shot) and 0.23 (Chain-of-Code).
F7: Reasoning model o4-mini achieved 87.5% with SOLAR (vs 91.7% zero-shot, 93.8% Chain-of-Code).
___

LIMITATIONS
Only what the authors explicitly state. Quote or close paraphrase.
L1: "This feasibility study deliberately targets calculation-oriented legal reasoning in well-defined statutory domains, using tax law as an ideal testbed."
L2: "Our single domain focus limits generalizability beyond calculation-oriented legal tasks, while our single ontology design prevents broader conclusions about construction methodologies."
L3: "The dataset size (96 cases) requires replication for robust validation."
L4: "Two models (Claude-3.7-Sonnet and LLaMA-4-Maverick) could not complete the SOLAR pipeline due to structured output compatibility issues, highlighting current implementation constraints."
___

DATASET / DOMAIN
Document type (contracts, case law, regulations, other): Statutory tax law — U.S. federal tax code calculations.
Legal domain or jurisdiction if specified: United States federal tax law.
Matches target domain (contracts / legal docs)? PARTIAL — statutory reasoning rather than contracts, but methodology (ontology-based legal reasoning) is transferable to contract analysis.
___

PRODUCT SIGNALS
One product implication per finding. Factual only, no speculation.
F1 → Ontology-based decomposition enables foundational models to approach reasoning-model performance (76.4% vs 87.0%) on structured legal tasks, at lower cost.
F2 → 45% token reduction vs zero-shot means lower cost per query and faster time-to-first-token for users.
F3 → Explicit inspection points (TBox, ABox, inference trace) enable verification of each reasoning step — critical for legal audit/compliance.
F4 → Performance democratization (68.2pp gap reduced to 5.9pp) means cheaper models become viable for legal reasoning tasks.
F5 → TBox interpreter (Python code) ensures consistent rule application across cases, unlike neural-only approaches.
___

TECHNOLOGY READINESS
READY = implementable today with existing libraries
NEAR = 6-12 months of integration work needed
RESEARCH = not production-ready, needs further study
F1: RESEARCH — TBox/ABox ontology construction pipeline requires per-statute effort and is not automated for arbitrary legal domains.
F2: READY — token efficiency is a natural consequence of representing statutes compactly in ontology form.
F3: NEAR — explicit verification points are a design property; building the verification UI and trace logging is integration work.
F4: NEAR — model democratization effect is real but pipeline complexity (multi-agent, SMT solver, code generation) is non-trivial.
F5: RESEARCH — generating correct Python TBox interpreters from statutory text is not reliably automated; current paper uses iterative refinement on training samples.
___

CONFLICT FLAGS
Does this paper contradict any earlier paper's finding?
If yes: state which paper [P-N] and exactly what conflicts.
If no: NONE
NONE
___

EVIDENCE GRADE
STRONG = peer-reviewed, large dataset, reproducible
MODERATE = solid but limited scope or dataset
WEAK = small dataset, single experiment, no replication
Grade: MODERATE
Reason (1 sentence): Proof-of-concept on single domain (tax law) with 96 cases, limited model compatibility (2 of 10 models failed), and single-ontology design limits claims about generalizability.
════════════════════════════════════════════
