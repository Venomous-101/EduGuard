# EduGuard UAE: Demo Video Script (7 minutes max)

## Structure: Problem (20%) → Live Demo (60%) → Impact (20%)

---

### [0:00-0:30] HOOK: The Problem

**[Visual: UAE classroom, students with tablets]**

"In 2025, the UAE made AI a compulsory subject from kindergarten to grade 12. The first country in the world to do so."

**[Visual: Headlines about AI in UAE schools]**

"But there's a gap. Schools are deploying AI tools, tutoring chatbots, automated grading, with no way to check if they're compliant with UAE law."

**[Visual: Question mark, policy documents]**

"Who checks that the AI grading your child follows the law? Nobody. Until now."

---

### [0:30-1:20] SOLUTION INTRO

**[Visual: EduGuard logo/URL]**

"EduGuard UAE is an evidence-anchored AI compliance agent for schools. A teacher pastes their AI use case. EduGuard checks it against 22 policy documents, UAE law, UNESCO, EU AI Act, and returns a verdict."

**[Visual: Architecture diagram (Y.3172)]**

"Every verdict is traced to verbatim policy citations. And the critical part: deterministic guardrails decide compliance, not the LLM. The AI can never override the rules."

---

### [1:20-5:30] LIVE DEMO (4 scenarios)

**Scenario 1: AI-only grading [1:20-2:30]**

**[Visual: Type into EduGuard]**
"Let's try a real case. A teacher wants AI to solely decide final exam grades, no human review."

**[Click Evaluate]**
**[Visual: NON_COMPLIANT verdict, R1 fired]**

"NON_COMPLIANT. Rule R1 fired: AI must not solely determine grades. Policy basis: EU AI Act Annex III. 12 citations retrieved."

**Scenario 2: Biometric monitoring [2:30-3:30]**

"Now facial recognition cameras to monitor student attention."

**[Visual: NON_COMPLIANT, R2 fired]**

"NON_COMPLIANT. Emotion recognition in education is prohibited. The system cites the exact policy text."

**Scenario 3: Child safety [3:30-4:30]**

"This is critical. A submission describing sexual content involving students."

**[Visual: NON_COMPLIANT, R7 child-safety fired]**

"Zero tolerance. NON_COMPLIANT. The system refuses to mark this compliant and recommends escalation to safeguarding authorities."

**Scenario 4: Compliant plan [4:30-5:30]**

"Now a responsible use case. Teacher uses AI for lesson ideas, reviews all output, enters no student data."

**[Visual: COMPLIANT verdict]**

"COMPLIANT. No rules fired. The system correctly distinguishes responsible AI use from violations."

---

### [5:30-6:30] AUDITABILITY & EVIDENCE

**[Visual: Audit log JSONL]**

"Every evaluation writes to an append-only audit log. Run ID, timestamps, retrieved chunks, fired rules, final verdict. Any regulator can replay exactly how a verdict was reached."

**[Visual: Citations section]**

"And every claim carries a verbatim citation with source URL. If the knowledge base has no relevant policy, the system says INSUFFICIENT_EVIDENCE instead of inventing an answer."

---

### [6:30-7:00] IMPACT & CLOSE

**[Visual: UAE schools, future vision]**

"EduGuard is designed for deployment, not just demo. Phase 1: harden and pilot with UAE schools. Phase 2: live station at the 2027 Summit multi-country exercise."

"Evidence-anchored. Deterministic. Auditable. That's how you build trust in AI for education."

**[Visual: GitHub URL, contact]**

"EduGuard UAE. Public on GitHub. MIT licensed."

**[END]**

---

## Production notes

- Record at 1080p, clear audio
- Live demo preferred; keep a backup screen recording
- Memorize first and last 20 seconds
- Rehearse 3x with timer, once with wifi off
- Total: under 7:00 (aim for 6:30)
