"""Reporter: assembles the final verdict.

Evidence-anchoring rule (the #1 winning trait): the report NEVER states a
policy claim without a verbatim citation from the KB or from a codified
guardrail rule. Where the KB has no relevant policy, the verdict section
explicitly says INSUFFICIENT_EVIDENCE instead of inventing one.
"""


class Reporter:
    def build(self, lesson_plan, context, retrieval, gap_analysis, rule_verdict, fired_rules):
        citations = []
        for h in retrieval["hits"]:
            citations.append({
                "title": h["title"],
                "source_url": h["source_url"],
                "verbatim_excerpt": h["text"][:500],
                "chunk_id": h["chunk_id"],
            })

        if retrieval["retrieval_confidence"] == "none":
            evidence_note = ("INSUFFICIENT_EVIDENCE: the knowledge base contains no policy "
                             "relevant to this submission. No policy claim is made.")
        else:
            evidence_note = (f"{len(citations)} policy excerpts retrieved; "
                             "all claims below are anchored to the verbatim citations listed.")

        findings = gap_analysis.get("findings", [])

        # Verdict semantics: a COMPLIANT verdict requires BOTH no fired rules
        # AND relevant retrieved policy. If the KB has nothing relevant,
        # compliance cannot be positively established -> NEEDS_REVIEW.
        if rule_verdict == "COMPLIANT" and retrieval["retrieval_confidence"] == "none":
            final_verdict = "NEEDS_REVIEW"
        else:
            final_verdict = rule_verdict

        report = {
            "verdict": final_verdict,  # COMPLIANT | NEEDS_REVIEW | NON_COMPLIANT (deterministic)
            "evidence_note": evidence_note,
            "deterministic_rules_fired": [
                {
                    "rule_id": fr["rule_id"],
                    "severity": fr["severity"],
                    "title": fr["title"],
                    "guidance": fr["guidance"],
                    "policy_basis": fr["policy_basis"],
                }
                for fr in fired_rules
            ],
            "advisory_gap_findings": [
                {
                    "type": f.get("type"),
                    "summary": f.get("summary"),
                    "verbatim_quote": f.get("verbatim_quote"),
                    "source_title": f.get("source_title"),
                    "source_url": f.get("source_url"),
                }
                for f in findings
            ],
            "citations": citations,
            "recommended_actions": self._actions(final_verdict, fired_rules, retrieval),
        }
        return report

    def _actions(self, verdict, fired_rules, retrieval=None):
        if verdict == "NON_COMPLIANT":
            return [
                "Do not deploy as described. Redesign the flagged elements: " +
                "; ".join(fr["title"] for fr in fired_rules if fr["severity"] == "NON_COMPLIANT"),
                "Resubmit for re-evaluation after redesign.",
            ]
        if verdict == "NEEDS_REVIEW":
            if retrieval and retrieval.get("retrieval_confidence") == "none" and not fired_rules:
                return [
                    "INSUFFICIENT_EVIDENCE: the knowledge base has no relevant policy "
                    "for this use case. Manual policy review is required before deployment.",
                ]
            return [
                "Human review required before deployment: " +
                "; ".join(fr["title"] for fr in fired_rules if fr["severity"] == "NEEDS_REVIEW"),
            ]
        return ["No blocking issues found against the current policy corpus. Keep monitoring for policy updates."]
