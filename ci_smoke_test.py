"""CI smoke test: guardrail checks + secrets scan. Run with: python ci_smoke_test.py"""
import re
import sys
from pathlib import Path

from guardrails.compliance_checker import ComplianceChecker


def test_guardrails():
    c = ComplianceChecker()
    v, _ = c.evaluate(
        "The AI chatbot will solely decide each student final exam grade with no human review.",
        "Grade 10",
    )
    assert v == "NON_COMPLIANT", f"grading: {v}"
    v, _ = c.evaluate(
        "Install facial recognition cameras to monitor student attention during lessons.",
        "Grade 8",
    )
    assert v == "NON_COMPLIANT", f"biometric: {v}"
    v, _ = c.evaluate(
        "Upload student records including names and grades to a third-party AI tutoring app.",
        "Grade 5",
    )
    assert v == "NEEDS_REVIEW", f"data: {v}"
    print("guardrail smoke tests: PASS")


def test_no_secrets():
    # Match likely API keys: sk- followed by 16+ alphanumerics, or api_key = "value"
    # Avoid false positives like "risk-use" in URLs.
    pattern = re.compile(r"sk-[A-Za-z0-9]{16,}|api_key\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE)
    roots = ["agents", "api", "kb", "guardrails", "audit"]
    bad = []
    for root in roots:
        for p in Path(root).rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="replace")
            if pattern.search(text):
                bad.append(str(p))
    assert not bad, f"possible secrets in: {bad}"
    print("secrets scan: PASS")


if __name__ == "__main__":
    test_guardrails()
    test_no_secrets()
    print("CI smoke tests: ALL PASS")
