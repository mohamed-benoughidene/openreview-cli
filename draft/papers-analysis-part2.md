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
