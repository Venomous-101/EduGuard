"""GapAnalyzer: compares a submitted lesson plan against retrieved policy.

Uses the LLM when available; otherwise produces an extractive comparison
from the retrieved chunks (no invented analysis). Output is a list of
candidate findings, each tied to verbatim citations. Findings are ADVISORY:
the deterministic ComplianceChecker (guardrails/) has the final say.
"""
from agents.llm import LLMBackend

SYSTEM_PROMPT = """You are a policy gap analyst for AI use in UAE schools.
You compare a teacher's submitted lesson plan against VERBATIM policy excerpts.
Rules:
- Every finding MUST quote the exact policy text it relies on (copy it exactly).
- NEVER invent a law, article number, or URL. If no excerpt supports a point, say INSUFFICIENT_EVIDENCE.
- Distinguish: (a) direct conflicts with policy, (b) gaps where policy is silent, (c) good alignment.
- Output JSON only: {"findings": [{"type": "conflict|gap|aligned", "summary": "...", "verbatim_quote": "...", "source_title": "...", "source_url": "..."}]}"""


class GapAnalyzer:
    def __init__(self, llm=None):
        self.llm = llm or LLMBackend()

    def analyze(self, lesson_plan, context, retrieval):
        hits = retrieval["hits"]
        if not hits:
            return {
                "findings": [],
                "llm_available": False,
                "note": "INSUFFICIENT_EVIDENCE: no relevant policy retrieved from KB.",
            }
        excerpts = "\n\n".join(
            f"[{h['title']}] ({h['source_url']})\n{h['text']}"
            for h in hits[:6]
        )
        user_prompt = (
            f"LESSON PLAN / CLASSROOM AI USE CASE:\n{lesson_plan}\n\n"
            f"CONTEXT: {context}\n\n"
            f"POLICY EXCERPTS:\n{excerpts}"
        )
        text = self.llm.generate(SYSTEM_PROMPT, user_prompt, max_tokens=1200)
        if text is None:
            return self._extractive_fallback(lesson_plan, hits)
        import json, re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        try:
            parsed = json.loads(m.group(0)) if m else {"findings": []}
        except Exception:
            parsed = {"findings": [], "raw": text[:500]}
        parsed["llm_available"] = True
        # Validate: every finding must carry a verbatim quote + source URL,
        # AND the quote must actually appear in the retrieved chunks.
        # This enforces evidence-anchoring: a hallucinated quote is rejected.
        chunk_texts = [h["text"] for h in hits]
        valid = []
        for f in parsed.get("findings", []):
            quote = (f.get("verbatim_quote") or "").strip()
            if quote and f.get("source_url") and self._quote_in_chunks(quote, chunk_texts):
                valid.append(f)
            else:
                f["type"] = "gap"
                f["verbatim_quote"] = ""
                f["summary"] = (f.get("summary") or "") + " [INSUFFICIENT_EVIDENCE: quote not found in retrieved policy]"
                valid.append(f)
        parsed["findings"] = valid
        return parsed

    @staticmethod
    def _quote_in_chunks(quote, chunk_texts):
        """Normalized substring check: quote must appear verbatim in some chunk."""
        def norm(s):
            import re
            return re.sub(r"\s+", " ", s).strip().lower()
        nq = norm(quote)
        # Require a meaningful length to avoid trivial matches
        if len(nq) < 20:
            return False
        return any(nq in norm(c) for c in chunk_texts)

    def _extractive_fallback(self, lesson_plan, hits):
        """No LLM reachable: return the raw excerpts as candidate evidence."""
        return {
            "findings": [
                {
                    "type": "gap",
                    "summary": "Policy excerpt relevant to this use case. Review the quoted text against your plan.",
                    "verbatim_quote": h["text"][:400],
                    "source_title": h["title"],
                    "source_url": h["source_url"],
                }
                for h in hits[:4]
            ],
            "llm_available": False,
            "note": "Extractive mode: showing verbatim policy excerpts. Deterministic guardrails above are authoritative.",
        }
