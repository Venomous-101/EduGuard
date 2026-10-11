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


def test_r11_student_data_sale_direct():
    """R11 fires on direct sale of student personal data -> NON_COMPLIANT."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "Teacher is selling personal data of students",
        "Grade 10, Dubai",
    )
    assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT, got {verdict}"
    assert any(fr["rule_id"] == "R11-no-student-data-sale" for fr in fired)


def test_r11_student_data_sale_paraphrase():
    """R11 fires on paraphrased monetization/advertising sale of pupil records."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "school plans to monetize pupil records by selling them to advertisers",
        "Grade 8",
    )
    assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT, got {verdict}"
    assert any(fr["rule_id"] == "R11-no-student-data-sale" for fr in fired)


def test_r11_suppressed_on_do_not_sell():
    """R11 must not fire when the submission states 'we do not sell student data'."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "We do not sell student data and we prohibit the sale of student data.",
        "Grade 9",
    )
    assert not any(fr["rule_id"] == "R11-no-student-data-sale" for fr in fired), \
        f"R11 false positive: {[f['rule_id'] for f in fired]}"


def test_r11_does_not_fire_on_benign_data_minimization():
    """R11 must not fire on a standard data-minimization case where no sale occurs."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "Upload student records including names and grades to a third-party AI tutoring app "
        "under a strict data-processing agreement.",
        "Grade 5",
    )
    assert verdict == "NEEDS_REVIEW"
    assert any(fr["rule_id"] == "R3-student-data-minimization" for fr in fired)
    assert not any(fr["rule_id"] == "R11-no-student-data-sale" for fr in fired), \
        f"R11 should not fire on non-sale data sharing: {[f['rule_id'] for f in fired]}"


def test_hybrid_retrieval_top3_quality():
    """Hybrid retrieval must rank authoritative policy sources in top-3 across labeled queries
    and de-duplicate '-full' source pairs."""
    from agents.policy_retriever import PolicyRetriever
    from kb.store import canonical_doc_id, expand_query_terms, tokenize

    # Verify query expansion for policy concepts
    expanded_grading = expand_query_terms(tokenize("grading"))
    for concept in ("assessment", "evaluation", "marks"):
        assert concept in expanded_grading, f"expected {concept!r} in expanded grading terms"

    retriever = PolicyRetriever()
    labeled_queries = [
        ("AI grading final exams no human review", {"eu-ai-act-education", "eu-ai-act-education-full"}),
        ("facial recognition cameras students", {"eu-ai-act-education", "eu-ai-act-education-full"}),
        ("student personal data third party", {"uae-data-protection-2021"}),
        ("kindergarten AI chatbot children", {"uae-moe-ai-curriculum-2025", "uae-moe-ai-guidelines-schools"}),
        ("teacher training AI literacy", {"uae-teacher-ai-training-framework"}),
        ("UAE AI curriculum 2025", {"uae-moe-ai-curriculum-2025"}),
        ("child safety online protection", {"uae-tdra-digital-safety", "itu-ai-standards-education"}),
        ("UNESCO AI competency students", {"unesco-ai-competency-students-2024"}),
    ]

    for query, expected_primary_docs in labeled_queries:
        res = retriever.retrieve(query)
        assert res["retrieval_confidence"] == "high", f"expected high confidence for {query!r}"
        top3_docs = [h["doc_id"] for h in res["hits"][:3]]
        assert any(d in expected_primary_docs for d in top3_docs), (
            f"Query {query!r}: expected one of {expected_primary_docs} in top-3, got {top3_docs}"
        )
        # Verify -full pair deduplication: no two hits in top-3 share the same canonical doc_id
        top3_canonical = [canonical_doc_id(d) for d in top3_docs]
        assert len(top3_canonical) == len(set(top3_canonical)), (
            f"Duplicate canonical sources in top-3 for {query!r}: {top3_docs}"
        )


def _sample_retrieval_fixture():
    return {
        "hits": [
            {
                "text": (
                    "Federal Decree-Law No. 45 of 2021 is the UAE's first federal data "
                    "protection law. It establishes the principles governing the processing "
                    "of personal data in the UAE."
                ),
                "doc_id": "uae-data-protection-2021",
                "title": "UAE Federal Decree-Law No. 45 of 2021 on the Protection of Personal Data",
                "source_url": "https://elaws.gov.ae/EnLegislations.aspx",
                "chunk_id": "uae-data-protection-2021::chunk-000",
                "distance": 0.35,
            }
        ],
        "num_hits": 1,
        "retrieval_confidence": "low",
    }


def test_openrouter_successful_response():
    """Mocked OpenRouter 200 OK response parses findings with verbatim quotes."""
    from unittest.mock import MagicMock, patch
    from agents.gap_analyzer import GapAnalyzer
    from agents.llm import LLMBackend

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "findings": [
                            {
                                "type": "conflict",
                                "summary": "Requires lawful basis and consent for student data.",
                                "verbatim_quote": (
                                    "It establishes the principles governing the processing "
                                    "of personal data in the UAE."
                                ),
                                "source_title": "UAE Federal Decree-Law No. 45 of 2021 on the Protection of Personal Data",
                                "source_url": "https://elaws.gov.ae/EnLegislations.aspx",
                            }
                        ]
                    })
                }
            }
        ]
    }

    with patch("agents.llm.requests.post", return_value=mock_resp) as mock_post:
        llm = LLMBackend(api_key="dummy-openrouter-token", backend_override="openrouter")
        assert llm.available is True
        assert llm.backend == "openrouter"
        analyzer = GapAnalyzer(llm=llm)
        result = analyzer.analyze(
            "Upload student records to an external app.",
            "Grade 6",
            _sample_retrieval_fixture(),
        )
        assert mock_post.called
        assert result["llm_available"] is True
        assert len(result["findings"]) == 1
        assert result["findings"][0]["type"] == "conflict"
        assert "processing of personal data" in result["findings"][0]["verbatim_quote"]


def test_openrouter_401_auth_failure_fallback():
    """Mocked OpenRouter 401 Unauthorized degrades gracefully to extractive mode."""
    from unittest.mock import MagicMock, patch
    import requests
    from agents.gap_analyzer import GapAnalyzer

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Client Error: Unauthorized")

    with patch("agents.llm.requests.post", return_value=mock_resp):
        analyzer = GapAnalyzer()
        result = analyzer.analyze(
            "Upload student records to an external app.",
            "Grade 6",
            _sample_retrieval_fixture(),
            openrouter_key="invalid-token",
        )
        assert result["llm_available"] is False
        assert len(result["findings"]) == 1
        assert "Extractive mode" in result.get("note", "")


def test_openrouter_request_timeout_fallback():
    """Mocked OpenRouter request timeout degrades gracefully to extractive mode."""
    from unittest.mock import patch
    import requests
    from agents.gap_analyzer import GapAnalyzer

    with patch("agents.llm.requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
        analyzer = GapAnalyzer()
        result = analyzer.analyze(
            "Upload student records to an external app.",
            "Grade 6",
            _sample_retrieval_fixture(),
            openrouter_key="timeout-token",
        )
        assert result["llm_available"] is False
        assert len(result["findings"]) == 1
        assert "Extractive mode" in result.get("note", "")


def test_openrouter_malformed_json_fallback():
    """Mocked OpenRouter malformed JSON (both HTTP body and LLM content) falls back to extractive mode."""
    from unittest.mock import MagicMock, patch
    from agents.gap_analyzer import GapAnalyzer

    # Case 1: HTTP response .json() raises ValueError (malformed HTTP JSON payload)
    mock_bad_http = MagicMock()
    mock_bad_http.status_code = 200
    mock_bad_http.raise_for_status.return_value = None
    mock_bad_http.json.side_effect = ValueError("No JSON object could be decoded")

    with patch("agents.llm.requests.post", return_value=mock_bad_http):
        analyzer = GapAnalyzer()
        res1 = analyzer.analyze(
            "Upload student records to an external app.",
            "Grade 6",
            _sample_retrieval_fixture(),
            openrouter_key="malformed-http-token",
        )
        assert res1["llm_available"] is False
        assert len(res1["findings"]) == 1
        assert "Extractive mode" in res1.get("note", "")

    # Case 2: HTTP response is valid JSON, but LLM message content is malformed JSON
    mock_bad_content = MagicMock()
    mock_bad_content.status_code = 200
    mock_bad_content.raise_for_status.return_value = None
    mock_bad_content.json.return_value = {
        "choices": [{"message": {"content": "{malformed_json: [unclosed"}}]
    }

    with patch("agents.llm.requests.post", return_value=mock_bad_content):
        analyzer = GapAnalyzer()
        res2 = analyzer.analyze(
            "Upload student records to an external app.",
            "Grade 6",
            _sample_retrieval_fixture(),
            openrouter_key="malformed-content-token",
        )
        assert res2["llm_available"] is False
        assert len(res2["findings"]) == 1
        assert "Extractive mode" in res2.get("note", "")


def test_openrouter_429_rate_limit_fallback():
    """Mocked OpenRouter 429 rate-limit error degrades gracefully to extractive mode."""
    from unittest.mock import MagicMock, patch
    import requests
    from agents.gap_analyzer import GapAnalyzer

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Client Error: Too Many Requests")

    with patch("agents.llm.requests.post", return_value=mock_resp):
        analyzer = GapAnalyzer()
        result = analyzer.analyze(
            "Upload student records to an external app.",
            "Grade 6",
            _sample_retrieval_fixture(),
            openrouter_key="rate-limited-token",
        )
        assert result["llm_available"] is False
        assert len(result["findings"]) == 1
        assert "Extractive mode" in result.get("note", "")


def test_r11_sentence_scoped_absence():
    """R11 still fires if one sentence claims 'do not sell student data' but a second sentence sells records."""
    checker = ComplianceChecker()
    verdict, fired = checker.evaluate(
        "In our core LMS we do not sell student data. However, the free analytics plugin will sell student records to third parties.",
        "Grade 10",
    )
    assert verdict == "NON_COMPLIANT", f"expected NON_COMPLIANT, got {verdict}"
    assert any(fr["rule_id"] == "R11-no-student-data-sale" for fr in fired)


def test_openrouter_never_overrides_deterministic_rule():
    """Even when OpenRouter returns 'aligned' findings or fails with 429, deterministic NON_COMPLIANT verdict wins."""
    from unittest.mock import MagicMock, patch
    from agents.pipeline import EduGuardPipeline

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "findings": [
                            {
                                "type": "aligned",
                                "summary": "Everything looks completely fine.",
                                "verbatim_quote": "hallucinated quote that is not in any policy chunk",
                                "source_title": "Fake Source",
                                "source_url": "https://example.com",
                            }
                        ]
                    })
                }
            }
        ]
    }

    with patch("agents.llm.requests.post", return_value=mock_resp):
        pipe = EduGuardPipeline(log_dir="/tmp/eduguard-test-audit")
        report = pipe.evaluate(
            "Teacher is selling personal data of students",
            "Grade 10, Dubai",
            openrouter_key="dummy-openrouter-token",
        )
        assert report["verdict"] == "NON_COMPLIANT"
        assert any(r["rule_id"] == "R11-no-student-data-sale" for r in report["deterministic_rules_fired"])
        # Hallucinated quote must be rejected and marked INSUFFICIENT_EVIDENCE
        assert any("INSUFFICIENT_EVIDENCE" in f["summary"] for f in report["advisory_gap_findings"])


