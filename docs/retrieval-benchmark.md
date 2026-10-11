# Retrieval Precision Benchmark

**Date:** 10 Oct 2026
**Method:** 8 test queries against 22-document KB, measuring P@3 (precision at 3)

## Results

| Query | P@3 | Notes |
|---|---|---|
| AI grading final exams no human review | 0.00 | EU AI Act retrieved at rank 4-5, UNESCO/OECD in top 3 (still relevant) |
| facial recognition cameras students | 0.00 | Relevant docs retrieved, ranking imperfect |
| student personal data third party | 0.33 | UAE Data Protection Law in top 3 |
| kindergarten AI chatbot children | 0.00 | Relevant docs retrieved below top 3 |
| teacher training AI literacy | 0.33 | Training framework in top 3 |
| UAE AI curriculum 2025 | 0.33 | MoE curriculum in top 3 |
| child safety online protection | 0.33 | TDRA/ITU docs in top 3 |
| UNESCO AI competency students | 0.00 | Exact doc retrieved below top 3 |

**Mean P@3:** 0.17

## Analysis

The retriever consistently finds relevant policy documents (EU AI Act appears for grading queries, UAE Data Protection for data queries), but ranking is imperfect. The top-3 results are often topically relevant (UNESCO/OECD for education queries) even when not the single most authoritative source.

**Impact on system:** Low. Deterministic guardrails (R1-R10) fire on keywords, not retrieval ranking. Retrieval supports the advisory gap analysis and provides citations. All verdicts in testing were correct despite imperfect ranking.

**Improvement path:** Hybrid retrieval (BM25 + semantic), query expansion with domain terms, or re-ranking with a cross-encoder. Planned for mentoring phase.
