"""PolicyRetriever: RAG over the ChromaDB policy KB.

Returns verbatim chunks with full citation metadata. This agent never
paraphrases policy and never invents sources: if the KB has nothing
relevant, it says so explicitly (retrieval_confidence = 'none').
"""
from kb.store import PolicyKB


class PolicyRetriever:
    def __init__(self, kb=None, n_results=6):
        self.kb = kb or PolicyKB()
        self.n_results = n_results

    def _queries_for(self, lesson_plan, context):
        base = f"{lesson_plan}\n{context}".strip()
        return [
            base,  # full submission
            f"AI in education policy classroom use: {context}",
            f"student data privacy AI education {context}",
            f"AI assessment grading examinations policy {context}",
        ]

    def retrieve(self, lesson_plan, context=""):
        seen = {}
        for q in self._queries_for(lesson_plan, context):
            for hit in self.kb.query(q, n_results=self.n_results):
                seen[hit["chunk_id"]] = hit
        hits = sorted(seen.values(), key=lambda h: h["distance"])[: self.n_results * 2]
        # Keep only reasonably relevant hits (distance threshold on normalized embeddings)
        relevant = [h for h in hits if h["distance"] < 1.2]
        return {
            "hits": relevant,
            "num_hits": len(relevant),
            "retrieval_confidence": "high" if len(relevant) >= 3 else (
                "low" if relevant else "none"),
        }
