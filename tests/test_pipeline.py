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


def test_insufficient_evidence_path():
    """When the KB has no relevant policy, verdict must be NEEDS_REVIEW (not COMPLIANT)."""
    from agents.reporter import Reporter
    reporter = Reporter()
    # Simulate empty retrieval
    retrieval = {"hits": [], "retrieval_confidence": "none"}
    gap = {"findings": [], "llm_available": False}
    report = reporter.build(
        "Completely unrelated gibberish xyzzy qwerty",
        "Mars",
        retrieval,
        gap,
        "COMPLIANT",  # no rules fired
        [],
    )
    assert report["verdict"] == "NEEDS_REVIEW", f"expected NEEDS_REVIEW, got {report['verdict']}"
    assert "INSUFFICIENT_EVIDENCE" in report["evidence_note"]
    assert any("INSUFFICIENT_EVIDENCE" in a for a in report["recommended_actions"])
    print("insufficient-evidence path OK")


def test_child_safety_rule():
    """R7: sexual content involving minors must ALWAYS be NON_COMPLIANT."""
    from guardrails.compliance_checker import ComplianceChecker
    c = ComplianceChecker()
    verdict, fired = c.evaluate(
        "Teacher is urging students for adult content sexual and asking to perform sex",
        "Grade 10, Dubai",
    )
    assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT, got {verdict}"
    assert any(f["rule_id"] == "R7-child-safety" for f in fired), "R7 must fire"
    # Legitimate health education with consent must NOT trigger R7
    verdict2, fired2 = c.evaluate(
        "Teacher will discuss sexual health education following the approved curriculum with parental consent",
        "Grade 10",
    )
    assert not any(f["rule_id"] == "R7-child-safety" for f in fired2), "R7 false positive on legit health ed"
    print("child-safety rule OK")

def test_paraphrased_ai_only_grading():
    """R1 must catch paraphrased AI-only grading, not just keyword phrases."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "The chatbot alone decides each student's final mark, with no teacher involvement.",
        "Grade 11",
    )
    assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT, got {verdict}: {fired}"
    assert any(fr["rule_id"] == "R1-no-unreviewed-ai-grading" for fr in fired)


def test_r5_scoped_to_matched_sentence():
    """R5 fires when deployment lacks teacher training, even if 'training' is
    mentioned elsewhere (e.g. for students) in a different sentence."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "We will deploy a new AI tool in all classrooms next term. Separately, "
        "students receive AI ethics training modules.",
        "Grade 9",
    )
    assert verdict == "NEEDS_REVIEW", f"expected NEEDS_REVIEW, got {verdict}: {fired}"
    assert any(fr["rule_id"] == "R5-teacher-ai-literacy" for fr in fired)


def test_r5_suppressed_when_training_in_same_sentence():
    """R5 stays suppressed when training is part of the same deployment plan."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "We will deploy a new AI tool in all classrooms next term, after every "
        "teacher completes a training workshop.",
        "Grade 9",
    )
    assert verdict == "COMPLIANT", f"expected COMPLIANT, got {verdict}: {fired}"


def test_r8_hallucination_risk_fires():
    """R8: AI-generated educational content without fact-checking -> NEEDS_REVIEW."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "The AI generates lesson content without fact-checking and students rely on ai answers without verification.",
        "Grade 6",
    )
    assert verdict == "NEEDS_REVIEW", f"expected NEEDS_REVIEW, got {verdict}"
    assert any(fr["rule_id"] == "R8-ai-hallucination-risk" for fr in fired)


def test_r8_suppressed_when_teacher_fact_checks():
    """R8 must not fire when the teacher fact-checks AI output."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "The AI generates lesson content without fact-checking, but the teacher fact-checks every AI output before class.",
        "Grade 6",
    )
    assert not any(fr["rule_id"] == "R8-ai-hallucination-risk" for fr in fired), \
        f"R8 false positive: {[f['rule_id'] for f in fired]}"


def test_r9_age_inappropriate_ai_tools():
    """R9: adult AI tools with young children and no age verification -> NEEDS_REVIEW."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "We will give young children using adult ai tools full access with no age verification.",
        "Grade 3",
    )
    assert verdict == "NEEDS_REVIEW", f"expected NEEDS_REVIEW, got {verdict}"
    assert any(fr["rule_id"] == "R9-age-inappropriate-ai-tools" for fr in fired)


def test_r9_suppressed_with_age_verification():
    """R9 must not fire when age verification / parental consent is in place."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "Children under 13 using generative ai with parental consent and age verification in place.",
        "Grade 4",
    )
    assert not any(fr["rule_id"] == "R9-age-inappropriate-ai-tools" for fr in fired), \
        f"R9 false positive: {[f['rule_id'] for f in fired]}"


def test_r10_high_stakes_disciplinary():
    """R10: AI-only disciplinary decisions -> NON_COMPLIANT."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "The AI decides disciplinary action and ai expels students automatically.",
        "Grade 9",
    )
    assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT, got {verdict}"
    assert any(fr["rule_id"] == "R10-no-unreviewed-high-stakes-decisions" for fr in fired)


def test_r10_high_stakes_admissions_and_special_needs():
    """R10 fires for admissions and special-needs determinations without human review."""
    checker = ComplianceChecker()
    for text in (
        "We use AI to screen admissions; ai decides admissions for new applicants.",
        "The AI diagnoses learning disabilities to determine special education eligibility.",
    ):
        verdict, fired = checker.evaluate(text, "School")
        assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT for {text!r}, got {verdict}"
        assert any(fr["rule_id"] == "R10-no-unreviewed-high-stakes-decisions" for fr in fired), \
            f"R10 did not fire for {text!r}"
