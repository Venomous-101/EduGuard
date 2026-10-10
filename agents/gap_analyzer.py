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
        # Validate: every finding must carry a verbatim quote + source URL
        valid = []
        for f in parsed.get("findings", []):
            if f.get("verbatim_quote") and f.get("source_url"):
                valid.append(f)
            else:
                f["type"] = "gap"
                f["summary"] = (f.get("summary") or "") + " [INSUFFICIENT_EVIDENCE: no verbatim citation]"
                valid.append(f)
        parsed["findings"] = valid
        return parsed

    def _extractive_fallback(self, lesson_plan, hits):
        """No LLM reachable: return the raw excerpts as candidate evidence."""
        return {
            "findings": [
                {
                    "type": "gap",
                    "summary": "LLM unavailable; manual review of retrieved policy required.",
                    "verbatim_quote": h["text"][:400],
                    "source_title": h["title"],
                    "source_url": h["source_url"],
                }
                for h in hits[:4]
            ],
            "llm_available": False,
        }
