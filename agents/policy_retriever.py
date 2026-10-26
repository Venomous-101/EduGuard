"""PolicyRetriever: RAG over the ChromaDB policy KB.

Returns verbatim chunks with full citation metadata. This agent never
paraphrases policy and never invents sources: if the KB has nothing
relevant, it says so explicitly (retrieval_confidence = 'none').
"""
from kb.store import (
    PolicyKB,
    deduplicate_full_pairs,
    expand_query_terms,
    tokenize,
)


class PolicyRetriever:
    def __init__(self, kb=None, n_results=6):
        self.kb = kb or PolicyKB()
        self.n_results = n_results

    def _queries_for(self, lesson_plan, context):
        base = f"{lesson_plan}\n{context}".strip()
        q_toks = tokenize(base)
        q_weights = expand_query_terms(q_toks)
        expanded = [t for t, w in q_weights.items() if t not in q_toks and w >= 0.5][:10]
        if expanded:
            return [base, f"{base} {' '.join(expanded)}"]
        return [base]

    def retrieve(self, lesson_plan, context=""):
        base = f"{lesson_plan}\n{context}".strip()
        hits = self.kb.query(base, n_results=self.n_results * 2)
        hits = deduplicate_full_pairs(hits)[: self.n_results * 2]
        # Keep only reasonably relevant hits (distance threshold on normalized embeddings)
        relevant = [h for h in hits if h["distance"] < 1.2]
        return {
            "hits": relevant,
            "num_hits": len(relevant),
            "retrieval_confidence": "high" if len(relevant) >= 3 else (
                "low" if relevant else "none"),
        }

