# EduGuard UAE

[![CI](https://github.com/Venomous-101/EduGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/Venomous-101/EduGuard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![ITU AI for Good](https://img.shields.io/badge/ITU-AI%20for%20Good%20Lab-blueviolet.svg)](https://www.itu.int/)

**Evidence-anchored AI compliance agent for UAE schools** - built for the ITU AI for Good Lab Hackathon (UAE edition).

A teacher or school admin submits an AI lesson plan or classroom AI use case. EduGuard checks it against UAE education AI policy, UNESCO AI competency frameworks, and EU AI Act education provisions. Every verdict carries **verbatim citations** from the knowledge base, or is explicitly marked `INSUFFICIENT_EVIDENCE`. Deterministic guardrails (plain code, not the LLM) enforce hard policy rules. Every retrieval, rule evaluation, and verdict is audit-logged.

> SIMULATION ONLY. All demo data is synthetic. No real student data is processed.

## Why this exists

The UAE made AI a **mandatory KG-12 subject from 2025-2026** and is investing billions of dirhams in AI development - yet its AI ethics frameworks are **nonbinding with no enforcement mechanism** (Atlantic Council). Schools deploying AI operate under high-ambition strategy with no operational compliance layer. EduGuard UAE is that layer.

## Architecture

```
lesson plan ──> PolicyRetriever ──> GapAnalyzer ──> ComplianceChecker ──> Reporter ──> verdict JSON
  (RAG over ChromaDB)   (LLM, advisory)   (DETERMINISTIC rules)   (cited verdict)
        │                      │                    │                    │
        └──────────────────────┴────────────────────┴────────────────────┘
                              audit log (JSONL, every stage)
```

1. **PolicyRetriever** (`agents/`): RAG over a ChromaDB knowledge base of real policy documents. Returns verbatim chunks with source URLs. Never paraphrases policy, never invents sources.
2. **GapAnalyzer** (`agents/`): LLM compares the submission against retrieved policy. Every finding must carry a verbatim quote + source URL, or it is downgraded to `INSUFFICIENT_EVIDENCE`. Advisory only. Falls back to extractive mode when no LLM is reachable.
3. **ComplianceChecker** (`guardrails/`): **deterministic rules engine in pure Python** - banned practices (biometric monitoring, AI-only grading), student-data rules, age-appropriate-use rules, AI-literacy duty, and a zero-tolerance child-safety rule. The LLM can never override these.
4. **Reporter** (`agents/`): assembles the verdict (`COMPLIANT` / `NEEDS_REVIEW` / `NON_COMPLIANT`; when no rule fires and the KB holds nothing relevant, the verdict is `NEEDS_REVIEW` with an `INSUFFICIENT_EVIDENCE` note), citations, recommended actions. Verdict precedence is deterministic.

**Evidence-anchoring rule (enforced in code):** the agent NEVER states a policy claim without a verbatim citation from the KB. LLM-produced quotes are verified against the retrieved chunks and stripped when they do not match verbatim.

## Knowledge base

`kb/sources/` holds policy documents (each with `DOC_ID`, `TITLE`, `SOURCE_URL` header). Current corpus (22 documents):

| doc_id | source |
|---|---|
| abudhabi-aiatc-mbzuai-education | Abu Dhabi AI Governance (AIATC) and MBZUAI Education Role |
| coe-ai-education-framework | Council of Europe AI and Education: Framework Convention |
| dubai-ai-policy-education | Dubai AI Policies and Education Initiatives |
| eu-ai-act-education | EU AI Act: Art. 4 (AI literacy) + Annex III education high-risk |
| eu-ai-act-education-full | EU AI Act (Regulation (EU) 2024/1689): full education provisions |
| itu-ai-standards-education | ITU AI for Good, AI Standards, and Child Online Protection |
| oecd-ai-education-principles | OECD AI Principles (2019, revised 2024) and Guidance on AI in Education |
| singapore-ai-education-framework | Singapore AI-in-Education Framework and National Approach |
| uae-ai-ethics-charter-2024 | UAE Charter for Development and Use of AI (2024) |
| uae-ai-strategy-2031-education | UAE National AI Strategy 2031 (education + governance) |
| uae-data-protection-2021 | UAE Federal Decree-Law No. 45 of 2021 (data protection principles) |
| uae-moe-ai-curriculum-2025 | UAE MoE: AI compulsory KG-12 (2025-2026) |
| uae-moe-ai-guidelines-schools | UAE MoE AI Guidelines and Curriculum for Schools |
| uae-tdra-digital-safety | UAE TDRA Digital Safety and Child Digital Safety Law |
| uae-teacher-ai-training-framework | UAE Teacher AI Training Framework (2025-2026 rollout) |
| uk-dfe-ai-education-guidance | UK DfE Guidance on Generative AI in Education (2025) |
| unesco-ai-competency-students-2024 | UNESCO AI Competency Framework for Students (2024) |
| unesco-ai-competency-teachers-2024 | UNESCO AI Competency Framework for Teachers (2024) |
| unesco-ethics-ai-recommendation-2021 | UNESCO Recommendation on the Ethics of AI (2021) |
| unesco-genai-guidance-2023 | UNESCO Guidance for Generative AI in Education and Research (2023) |
| unesco-genai-guidance-2023-full | UNESCO GenAI Guidance (2023): full key recommendations |
| unicef-ai-children-guidance | UNICEF Guidance on AI for Children |

## Quickstart

```bash
cd EduGuard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Ingest the knowledge base (local embeddings, no API key)
python -m kb.ingest

# 2. Run the API
uvicorn api.main:app --port 8000

# 3. Open http://localhost:8000  (demo UI)
#    POST /evaluate  {"lesson_plan": "...", "context": "..."}
```

Optional LLM for gap analysis (Ollama default; without it the pipeline still works deterministically):
```bash
ollama pull qwen2.5:7b
# or: EDUGUARD_LLM_BACKEND=openai  +  OPENAI_API_KEY=...  (never commit keys)
```

Run tests:
```bash
python -m pytest tests/ -x -q
```

## API

- `POST /evaluate` - `{lesson_plan: string, context: string}` -> verdict JSON (`COMPLIANT` / `NEEDS_REVIEW` / `NON_COMPLIANT`) with citations, fired rules, recommended actions, audit run id
- `GET /health` - KB chunk count, LLM availability
- `GET /sources` - KB documents with source URLs
- `GET /` - demo UI

## ITU standards alignment

- **Y.3172 ML pipeline mapping**: KB ingestion = data source nodes; the four agents = ML pipeline nodes; `EduGuardPipeline` = ML Function Orchestrator; error-scenario evaluations = ML sandbox (isolated test environment).
- **AI Readiness Framework**: the KB operationalizes the "standards-enabled stakeholder buy-in" and "sandbox and pilot experimentation" factors for the education domain.

## License

MIT. See LICENSE.
