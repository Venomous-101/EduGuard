"""Smoke tests for EduGuard UAE.

Run:  python -m pytest tests/ -x -q   (from eduguard/)
Requires: KB ingested (python -m kb.ingest), venv active.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guardrails.compliance_checker import ComplianceChecker


def test_non_compliant_ai_grading():
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "The AI chatbot will solely decide each student's final exam grade with no human review.",
        "Grade 10",
    )
    assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT, got {verdict}"
    assert any(fr["rule_id"] == "R1-no-unreviewed-ai-grading" for fr in fired)


def test_non_compliant_biometrics():
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "Install facial recognition cameras to monitor student attention during lessons.",
        "Grade 8",
    )
    assert verdict == "NON_COMPLIANT"
    assert any(fr["rule_id"] == "R2-no-biometric-monitoring" for fr in fired)


def test_needs_review_student_data():
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "Upload student records including names and grades to a third-party AI tutoring app.",
        "Grade 5",
    )
    assert verdict == "NEEDS_REVIEW"
    assert any(fr["rule_id"] == "R3-student-data-minimization" for fr in fired)


def test_kg_age_appropriate_flag():
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "Kindergarten children will chat unsupervised with an AI assistant for 30 minutes daily.",
        "KG",
    )
    assert verdict == "NEEDS_REVIEW"
    assert any(fr["rule_id"] == "R4-kg-age-appropriate" for fr in fired)


def test_compliant_plan():
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "Teacher uses an AI tool to brainstorm lesson ideas, reviews all AI-generated content "
        "before class, and does not enter any student personal data into the tool.",
        "Grade 7",
    )
    assert verdict == "COMPLIANT", f"expected COMPLIANT, got {verdict}: {fired}"


def test_full_pipeline_end_to_end():
    from agents.pipeline import EduGuardPipeline
    pipe = EduGuardPipeline(log_dir="/tmp/eduguard-test-audit")
    report = pipe.evaluate(
        "The AI will solely decide each student's final exam grade with no human review.",
        "Grade 10, Dubai",
    )
    assert report["verdict"] == "NON_COMPLIANT"
    assert len(report["citations"]) > 0, "expected KB citations"
    for c in report["citations"]:
        assert c["source_url"], "every citation must carry a source URL"
    assert os.path.exists(report["audit_log_path"])
    # audit log is valid JSONL
    with open(report["audit_log_path"]) as f:
        for line in f:
            json.loads(line)
    print("pipeline OK; audit:", report["audit_log_path"])
