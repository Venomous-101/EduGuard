"""EduGuard UAE pipeline orchestrator.

Flow:
  1. PolicyRetriever  (RAG over ChromaDB, verbatim chunks + citations)
  2. GapAnalyzer      (LLM advisory comparison; extractive fallback if no LLM)
  3. ComplianceChecker(DETERMINISTIC rules engine; LLM never overrides)
  4. Reporter         (verdict + citations, or INSUFFICIENT_EVIDENCE)

Every stage is audit-logged to JSONL.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.policy_retriever import PolicyRetriever  # noqa: E402
from agents.gap_analyzer import GapAnalyzer  # noqa: E402
from agents.reporter import Reporter  # noqa: E402
from guardrails.compliance_checker import ComplianceChecker  # noqa: E402
from audit.logger import AuditLogger  # noqa: E402
from kb.store import PolicyKB  # noqa: E402


class EduGuardPipeline:
    def __init__(self, log_dir=None):
        self.kb = PolicyKB()
        self.retriever = PolicyRetriever(kb=self.kb)
        self.analyzer = GapAnalyzer()
        self.checker = ComplianceChecker()
        self.reporter = Reporter()
        self.log_dir = log_dir

    def evaluate(self, lesson_plan, context=""):
        if not lesson_plan or not lesson_plan.strip():
            raise ValueError("lesson_plan must be a non-empty string")
        # Fresh audit logger per evaluation: isolates concurrent API requests
        # so each run gets its own run_id, sequence counter, and JSONL file.
        audit = AuditLogger(log_dir=self.log_dir)
        audit.log("input", "evaluation_started", {
            "lesson_plan_chars": len(lesson_plan),
            "context": context,
            "kb_chunks": self.kb.count(),
        })

        # 1. Retrieve
        retrieval = self.retriever.retrieve(lesson_plan, context)
        audit.log_retrieval(f"{lesson_plan[:120]} | {context}", retrieval["hits"])

        # 2. Gap analysis (advisory)
        gap = self.analyzer.analyze(lesson_plan, context, retrieval)
        audit.log("analysis", "gap_analysis_complete", {
            "llm_available": gap.get("llm_available"),
            "num_findings": len(gap.get("findings", [])),
        })

        # 3. Deterministic compliance check (authoritative)
        rule_verdict, fired_rules = self.checker.evaluate(lesson_plan, context)
        for fr in fired_rules:
            audit.log_rule_evaluation(fr["rule_id"], True, {
                "matched_keywords": fr["matched_keywords"],
                "severity": fr["severity"],
            })
        audit.log("rules", "all_rules_evaluated", {
            "num_fired": len(fired_rules),
            "verdict": rule_verdict,
        })

        # 4. Report
        report = self.reporter.build(
            lesson_plan, context, retrieval, gap, rule_verdict, fired_rules
        )
        audit.log_verdict(
            rule_verdict, report["citations"],
            f"{len(fired_rules)} rules fired; {len(gap.get('findings', []))} advisory findings",
        )
        report["audit_run_id"] = audit.run_id
        report["audit_log_path"] = audit.path
        return report
