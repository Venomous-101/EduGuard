# EduGuard UAE: Evidence-Anchored AI Compliance for Schools

**ITU AI for Good Lab Hackathon, United Arab Emirates, 2026**
**Technical Report**
**Ali Abdullah (solo participant, Education domain)**

---

## 1. Problem

In the 2025-2026 academic year, the United Arab Emirates made artificial intelligence a compulsory subject from kindergarten through grade 12, the first country in the world to do so. The Ministry of Education trained nearly 1,000 specialist teachers for the rollout. The ambition is historic.

The enforcement layer beneath that ambition is missing. The UAE's AI ethics frameworks, including the 2024 Charter for the Development and Use of AI, are nonbinding. Schools are deploying AI tools, from tutoring chatbots to automated grading, under high-ambition strategy documents with no operational compliance layer beneath them.

Three concrete risks follow. First, student data protection: AI EdTech vendors process children's personal data under Federal Decree-Law No. 45 of 2021, but schools have no practical tool to verify vendor compliance. Second, unreviewed automation: AI systems grade students or monitor exams without the meaningful human oversight international frameworks require. Third, age appropriateness: young children interact with AI assistants designed for adults, with no systematic check against curriculum guidance.

The gap is not a lack of policy. It is a lack of enforcement machinery. EduGuard UAE is that machinery: an evidence-anchored AI agent that evaluates classroom AI use cases against real policy documents and returns verdicts every school can act on.

## 2. Architecture

EduGuard evaluates a classroom AI use case and returns COMPLIANT, NEEDS_REVIEW, or NON_COMPLIANT. Every verdict is traceable to verbatim citations from a curated policy knowledge base, or the system explicitly marks evidence as insufficient. The design follows the pattern ITU rewarded at the September 2026 AI Readiness Hackathon in Riyadh: reliable evidence, regulatory alignment, local context, traceability, and meaningful human oversight.

### 2.1 Four-stage pipeline and Y.3172 mapping

The pipeline maps directly to ITU-T Y.3172 machine-learning pipeline nodes:

| Y.3172 node | EduGuard component | Function |
|---|---|---|
| SRC (data source) | 22 policy documents | UAE law, MoE guidance, UNESCO, EU AI Act, OECD, UNICEF |
| C (collector) + PP (preprocessor) | kb/ingest.py | Chunking (400 words, 60-word overlap), metadata validation |
| M (model) | kb/store.py + GapAnalyzer | ChromaDB retrieval with local ONNX embeddings; advisory LLM analysis |
| P (policy node) | guardrails/compliance_checker.py | 10 deterministic rules (pure Python, no LLM); authoritative verdict |
| D (distributor) | agents/reporter.py | Assembles cited verdict, recommended actions |
| SINK (action target) | Verdict + audit log | JSONL audit trail with run IDs, chunk IDs, fired rules |
| MLFO (orchestrator) | agents/pipeline.py | Sequences all stages |
| ML sandbox | tests/test_pipeline.py | 11 tests incl. adversarial scenarios |

The critical architectural decision is the P node: deterministic guardrails the LLM can never override. A language model alone can hallucinate policy; a rules engine alone cannot parse natural language. Together, the LLM provides understanding and the rules provide guarantees.

### 2.2 Deterministic guardrails (authoritative)

Ten rules encode the highest-risk patterns as pure Python:

| ID | Pattern | Verdict |
|---|---|---|
| R1 | AI solely decides grades, no human review | NON_COMPLIANT |
| R2 | Biometric or emotion-recognition monitoring of students | NON_COMPLIANT |
| R6 | AI-only exam proctoring decisions | NON_COMPLIANT |
| R7 | Sexual content, abuse, or exploitation involving minors (zero tolerance) | NON_COMPLIANT |
| R3 | Student personal data shared with third parties | NEEDS_REVIEW |
| R4 | Unsupervised AI use with kindergarten children | NEEDS_REVIEW |
| R5 | Classroom AI deployment without teacher AI-literacy training | NEEDS_REVIEW |
| R8 | AI-generated educational content without fact-checking | NEEDS_REVIEW |
| R9 | Adult-designed AI tools used with young children, no age verification | NEEDS_REVIEW |
| R10 | AI influences disciplinary, admissions, or special-needs decisions without human review | NEEDS_REVIEW |

Rules implement word-boundary matching (so "untrained" does not match "trained") and sentence-scoped negation handling ("we banned facial recognition cameras" correctly does not fire R2). Rule verdicts take absolute precedence over LLM output.

### 2.3 Evidence anchoring

The system never states a policy claim without a verbatim citation. GapAnalyzer findings must include quotes verified by substring match against retrieved chunks; hallucinated quotes are rejected and relabeled INSUFFICIENT_EVIDENCE. When the knowledge base has no relevant policy, the verdict is NEEDS_REVIEW (never a false COMPLIANT). Every pipeline stage writes to an append-only JSONL audit log.

### 2.4 Technology

Python 3.12, FastAPI, ChromaDB with fully local ONNX embeddings (no API key required). Pluggable LLM backend: Ollama by default, OpenAI via environment variable, or the user's own OpenRouter key supplied per-request in the UI (never stored). The system runs end to end with no LLM at all. Public repo, MIT license, zero API keys committed, 100 percent synthetic test data.

## 3. Knowledge Base

22 policy documents, 36 chunks, each carrying mandatory citation metadata (document ID, title, source URL). The ingestion pipeline refuses chunks without source URLs.

**UAE national and federal:** National AI Strategy 2031 (education provisions); MoE AI curriculum rollout 2025-2026; MoE AI guidelines for schools; Charter for the Development and Use of AI (2024); Federal Decree-Law No. 45 of 2021 (data protection); teacher AI training framework; TDRA digital safety and Child Digital Safety Law.

**Emirate level:** Dubai AI policy and education initiatives; Abu Dhabi AIATC and MBZUAI education role.

**International:** UNESCO GenAI guidance (2023); UNESCO AI competency frameworks for students and teachers (2024); UNESCO ethics recommendation (2021); EU AI Act education provisions; OECD AI principles and education guidance; UNICEF AI for children; ITU AI for Good and Child Online Protection; UK DfE AI guidance; Singapore AI education framework; Council of Europe framework convention.

The corpus is deliberately comparative: UAE policy as the local baseline, UNESCO/EU/OECD/UNICEF as the global reference layer. This structure enables the policy-gap identification the evaluation prioritizes. Arabic-language UAE sources are being added to strengthen local grounding.

## 4. Evaluation

### 4.1 Rule tests (11 passing)

| Scenario | Expected | Result |
|---|---|---|
| AI solely decides final grades, no human review | NON_COMPLIANT (R1) | PASS |
| Facial recognition cameras monitor attention | NON_COMPLIANT (R2) | PASS |
| Student records uploaded to third-party AI app | NEEDS_REVIEW (R3) | PASS |
| Kindergarten children unsupervised with AI | NEEDS_REVIEW (R4) | PASS |
| Responsible AI use (reviews output, no student data) | COMPLIANT | PASS |
| "Does not enter personal data" (negation) | No false positive | PASS |
| "We banned facial recognition" (negation) | No false positive | PASS |
| "Teachers are untrained" (word boundary) | NEEDS_REVIEW (R5 fires) | PASS |
| Sexual content involving minors | NON_COMPLIANT (R7) | PASS |
| Legitimate health education with consent | No R7 false positive | PASS |
| Empty retrieval | NEEDS_REVIEW + INSUFFICIENT_EVIDENCE | PASS |

### 4.2 End-to-end verification

Full pipeline on the AI-grading scenario: NON_COMPLIANT, R1 fired, 12 knowledge-base citations each with source URLs, valid JSONL audit log. API verified live: POST /evaluate returns verdict JSON, GET /health and /sources respond correctly, demo UI renders.

### 4.3 Adversarial testing

10/10 adversarial scenarios pass, including paraphrased violations ("the chatbot alone decides each student's final mark"), new AI deployment without training, and emotion-AI monitoring. Stress tests with 5,000-character inputs, repetitive text, and edge cases: 9/9 pass with no errors and sub-3-second response times.

### 4.4 Limitations

Keyword-based matching covers the highest-risk patterns but may miss novel paraphrases; rule coverage expands with mentor feedback. The LLM stage runs in extractive fallback when no model is reachable; LLM-backed analysis activates with Ollama or a user-supplied OpenRouter key. Arabic-language sources are in progress.

## 5. Deployment Roadmap and Responsible AI

### 5.1 Path to the 2027 Summit

**Phase 1 (now to 10 Nov deadline):** Harden MVP, expand rules, add Arabic sources, record demo video. Public deployment URL live for judges. **Phase 2 (mentoring through early 2027):** Pilot with UAE schools, validate rule precision against human expert review on anonymized teacher submissions. **Phase 3 (2027 Summit):** Deploy as a live station in the multi-country error exercise. The deterministic engine makes this feasible: fully reproducible behavior, a requirement for judged live exercises.

### 5.2 Responsible AI

EduGuard practices the oversight it enforces. No model output is presented as policy fact. Deterministic rules decide compliance, so the most consequential outputs are reproducible and auditable. All data is synthetic. NEEDS_REVIEW verdicts route to human decision-makers by design. The system is decision support for school leaders, never autonomous authority over children.

---

*Repository: github.com/Venomous-101/EduGuard (public, MIT). Demo, API docs, and audit samples in README.*
