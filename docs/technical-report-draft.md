# EduGuard UAE: Evidence-Anchored AI Compliance for Schools

**ITU AI for Good Lab Hackathon, United Arab Emirates, 2026**
**Technical Report (draft)**
**Author: Ali Abdullah (solo participant, Education domain)**

---

## 1. Problem

In the 2025-2026 academic year, the United Arab Emirates made artificial intelligence a compulsory subject from kindergarten through grade 12, the first country in the world to do so. Abu Dhabi allocated AED 13 billion to AI development, and the Ministry of Education trained nearly 1,000 specialist teachers for the rollout. The ambition is historic.

The enforcement layer beneath that ambition is missing. The UAE's AI ethics frameworks, including the 2024 Charter for the Development and Use of AI, are nonbinding. The Atlantic Council's assessment of the UAE's AI governance concludes that these frameworks "lack enforcement mechanisms, limiting their practical reach." Schools are therefore deploying AI tools, from tutoring chatbots to automated grading, under high-ambition strategy documents with no binding compliance layer beneath them.

This creates three concrete risks. First, student data protection: AI EdTech vendors process children's personal data under the UAE's Federal Decree-Law No. 45 of 2021, but schools have no practical tool to verify that a vendor's data practices comply. Second, unreviewed automation: AI systems that grade students or monitor exams operate without the meaningful human oversight that international frameworks require. Third, age appropriateness: kindergarten children interact with AI assistants designed for adults, with no systematic check against the Ministry's own curriculum guidance.

The gap is not a lack of policy. It is a lack of enforcement machinery. EduGuard UAE is that machinery: an evidence-anchored AI agent that evaluates classroom AI use cases against real policy documents and returns verdicts every school can act on.

## 2. Solution: Architecture

EduGuard UAE evaluates a teacher's or administrator's AI use case (for example, "an AI chatbot will solely decide final exam grades") and returns one of three verdicts: COMPLIANT, NEEDS_REVIEW, or NON_COMPLIANT. Every verdict is traceable to verbatim citations from a curated policy knowledge base, or the system explicitly marks the evidence as insufficient. The design follows the pattern the ITU rewarded at the September 2026 AI Readiness Hackathon in Riyadh: reliable evidence, regulatory alignment, local context, traceability, and meaningful human oversight.

### 2.1 Four-stage pipeline

**Stage 1: PolicyRetriever.** The submission is embedded locally and matched against a ChromaDB knowledge base of policy documents (Section 3). Retrieval returns verbatim text chunks, each carrying its source document title and URL as metadata. No paraphrase enters the pipeline at this stage; the agent works only with quoted policy text.

**Stage 2: GapAnalyzer (advisory).** A language model compares the submission against the retrieved policy chunks and produces structured findings, each required to include a verbatim quote. This stage is advisory only. If no language model is available, an extractive fallback surfaces the most relevant retrieved chunks directly. The LLM can never issue a verdict.

**Stage 3: ComplianceChecker (deterministic, authoritative).** Hard policy rules are encoded as pure Python, with no model involved. Six rules cover the highest-risk patterns: AI-only grading (NON_COMPLIANT), biometric or emotion-recognition monitoring of students (NON_COMPLIANT), AI-only exam proctoring decisions (NON_COMPLIANT), student personal data shared with third parties (NEEDS_REVIEW), AI use with kindergarten children (NEEDS_REVIEW), and classroom AI deployment without teacher AI-literacy training (NEEDS_REVIEW). The rules implement negation handling, so "does not enter any student personal data" correctly does not fire the data rule. Rule verdicts take precedence over everything the advisory LLM stage produces.

**Stage 4: Reporter.** The final report combines the deterministic verdict with the supporting citations. Where the knowledge base contains no relevant policy for a submission, the report states INSUFFICIENT_EVIDENCE rather than inventing an answer. This refusal behavior is deliberate: it is the mechanism that keeps the system honest.

### 2.2 Why this architecture

Separating probabilistic reasoning (the LLM) from deterministic enforcement (the rules engine) solves the central trust problem of AI compliance tools. A language model alone can hallucinate policy; a rules engine alone cannot understand natural-language submissions. Together, the LLM provides understanding and the rules provide guarantees. Every decision is written to an append-only JSONL audit log with timestamps, run IDs, retrieved chunk IDs, fired rules, and the final verdict, giving schools and regulators a complete trace of how each verdict was reached.

### 2.3 Technology stack

Python 3.12, FastAPI, ChromaDB with fully local ONNX embeddings (no API key required), and a pluggable LLM backend (Ollama by default, OpenAI optional via environment variable). The system runs end to end with no language model at all, using the extractive fallback. The repository is public under the MIT license, contains zero API keys, and uses 100 percent synthetic test data.

## 3. Knowledge Base: Sources and Curation

The knowledge base contains 22 policy documents (36 chunks), spanning UAE national strategy, UAE federal law, emirate-level policy, and international frameworks. Every chunk carries mandatory citation metadata (document ID, title, source URL); the ingestion pipeline refuses any chunk without a source URL.

### 3.1 Source list

**UAE national and federal:**
- UAE National AI Strategy 2031, education and governance provisions
- UAE Ministry of Education AI curriculum rollout 2025-2026 (AI as compulsory KG-12 subject)
- UAE Ministry of Education AI guidelines for schools
- UAE Charter for the Development and Use of AI (2024)
- UAE Federal Decree-Law No. 45 of 2021 on Personal Data Protection
- UAE teacher AI training framework (specialist teacher program)
- UAE TDRA digital safety and AI governance

**Emirate level:**
- Dubai AI policy (Digital Dubai AI ethics principles, Dubai AI Campus)
- Abu Dhabi AIATC and MBZUAI education role

**International frameworks:**
- UNESCO Guidance for Generative AI in Education and Research (2023)
- UNESCO AI Competency Frameworks for Students and Teachers (2024)
- UNESCO Recommendation on the Ethics of AI (2021)
- EU AI Act, education-relevant provisions (high-risk classification, prohibited practices)
- OECD AI Principles and AI in education guidance
- UNICEF Policy Guidance on AI for Children
- ITU AI for Good publications and Child Online Protection
- UK Department for Education AI in education guidance
- Singapore AI in education framework
- Council of Europe AI and education work

### 3.2 Curation method

Each source was researched from official publications and summarized as a factual document with a verified source URL. Documents are chunked with a sliding window (approximately 400 words, 60-word overlap) to preserve context. Embeddings are generated locally, so the entire knowledge base builds and queries without any external API. The source set is deliberately comparative: UAE policy provides the local baseline, while UNESCO, EU, OECD, and UNICEF instruments supply the global best practices against which gaps are identified. This comparative structure is what enables the policy-gap analysis the hackathon evaluation prioritizes.

## 4. Evaluation

### 4.1 Deterministic rule tests

Six test scenarios exercise the ComplianceChecker directly:

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 1 | AI chatbot solely decides final exam grades, no human review | NON_COMPLIANT (R1) | PASS |
| 2 | Facial recognition cameras monitor student attention | NON_COMPLIANT (R2) | PASS |
| 3 | Student records uploaded to third-party AI tutoring app | NEEDS_REVIEW (R3) | PASS |
| 4 | Kindergarten children chat unsupervised with AI assistant | NEEDS_REVIEW (R4) | PASS |
| 5 | Teacher uses AI for lesson ideas, reviews all output, enters no student data | COMPLIANT (no rule fires) | PASS |
| 6 | Negation handling: "does not enter personal data" does not fire R3 | No false positive | PASS |

All six pass. Scenario 5 is the critical control: a responsible AI use case must clear the system, not just risky ones must be caught.

### 4.2 End-to-end pipeline test

A full pipeline run on the AI-grading scenario returned NON_COMPLIANT with rule R1 fired, 8 knowledge-base citations each carrying a source URL, and a valid JSONL audit log (every line parses, run ID traceable). The API was verified live: POST /evaluate returns the verdict JSON, GET /sources lists all documents, and the demo page loads successfully.

### 4.3 Evidence-anchoring verification

The test suite asserts that every citation in every report carries a non-empty source URL, and that the INSUFFICIENT_EVIDENCE path triggers when the knowledge base has no relevant policy. No verdict in the test set was issued without either a fired deterministic rule or cited policy text.

### 4.4 Limitations

The keyword-based rule matcher covers the highest-risk patterns but will miss paraphrased violations outside its keyword lists; expanding rule coverage with mentor feedback during the mentoring window is planned. The GapAnalyzer LLM stage was tested in extractive fallback mode (no local model available in the build environment); LLM-backed analysis activates automatically when Ollama is present. The knowledge base, while broad, does not yet include Arabic-language UAE policy texts; adding them would strengthen local grounding.

## 5. Deployment Roadmap and Responsible AI

### 5.1 Path to the 2027 Summit live exercise

EduGuard UAE is designed as a deployable enforcement layer, not a demo. The roadmap has three phases. **Phase 1 (now to solution deadline):** harden the MVP, expand rule coverage with mentor input, add Arabic-language sources, and record the demo video. **Phase 2 (mentoring window through early 2027):** pilot with a small set of UAE schools, collecting real teacher submissions (anonymized) to validate rule precision and recall against human expert review. **Phase 3 (2027 Summit):** deploy as a live station in the multi-country error exercise, where participants submit AI classroom scenarios and watch the agent evaluate them in real time, with the audit log projected as the traceability demonstration. The deterministic rules engine makes this feasible: its behavior is fully reproducible, a requirement for a live judged exercise.

### 5.2 Responsible AI statement

EduGuard UAE practices the oversight it enforces. The system never presents model output as policy fact: every claim is either a verbatim citation or an explicit admission of insufficient evidence. The deterministic rules, not the language model, decide compliance, so the system's most consequential outputs are fully reproducible and auditable. All training and test data is synthetic; no real student data was used or is required. The audit log gives any regulator, school, or parent the complete reasoning trace behind any verdict. Human oversight is structural, not decorative: NEEDS_REVIEW verdicts route to a human decision-maker by design, and the system is positioned as decision support for school leaders, never as an autonomous authority over children.

---

*Word count: approximately 1,900. Formatted for 5 pages. No em-dashes used.*
