"""ComplianceChecker: DETERMINISTIC rules engine. No LLM involved.

Hard policy rules are encoded here as pure Python. The LLM (GapAnalyzer)
is advisory only and can NEVER override these rules. Each rule returns a
fired/not-fired result with the exact policy basis (doc_id + source URL),
so every NON_COMPLIANT verdict is traceable to a codified rule, not to
model output.

Verdict precedence: NON_COMPLIANT > NEEDS_REVIEW > COMPLIANT.
"""
import re

# Each rule: id, severity, policy_basis (doc_id + url), matcher keywords.
# A rule FIRES when its keywords match the submission text (case-insensitive).
RULES = [
    {
        "id": "R1-no-unreviewed-ai-grading",
        "severity": "NON_COMPLIANT",
        "title": "AI must not solely determine student grades or assessment outcomes",
        "policy_basis": {
            "doc_id": "eu-ai-act-education-full",
            "title": "EU AI Act (Regulation (EU) 2024/1689), Annex III point 3(b): evaluating learning outcomes",
            "source_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        },
        "keywords": [
            "solely decide", "solely determine", "final grade decided by ai",
            "ai decides the grade", "automatic grading without review",
            "no human review", "without teacher review", "no teacher review",
            "with no teacher review", "grade all final exams automatically",
            "no teacher checking", "without any human oversight",
            "determine student grades without", "ai will grade",
            "automatically grade", "grade students automatically",
            "alone decides each student", "alone decides the grade", "alone decides grades",
            "alone decides the final", "alone determines the grade", "alone determines grades",
            "alone determines the final", "fully automated grading",
            "end-to-end automated grading",
        ],
        "guidance": "AI systems evaluating learning outcomes are high-risk (EU AI Act Annex III, point 3(b)). "
                    "Grades must remain under meaningful human oversight; AI may assist but not solely determine outcomes.",
    },
    {
        "id": "R2-no-biometric-monitoring",
        "severity": "NON_COMPLIANT",
        "title": "No biometric identification or emotion recognition of students",
        "policy_basis": {
            "doc_id": "eu-ai-act-education-full",
            "title": "EU AI Act Article 5(1)(f): emotion inference in education and work is prohibited",
            "source_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        },
        "keywords": [
            "facial recognition", "face recognition", "emotion detection",
            "emotion recognition", "emotion ai", "biometric", "eye tracking for attention",
            "attention monitoring via camera", "detect if students are bored",
            "detect student emotions",
        ],
        "guidance": "Emotion inference and biometric identification in education are prohibited practices under the EU AI Act. "
                    "Classroom monitoring must not use biometrics.",
    },
    {
        "id": "R3-student-data-minimization",
        "severity": "NEEDS_REVIEW",
        "title": "Student personal data use requires consent and minimization",
        "policy_basis": {
            "doc_id": "uae-data-protection-2021",
            "title": "UAE Federal Decree-Law No. 45 of 2021 on Personal Data Protection (principles)",
            "source_url": "https://elaws.gov.ae/EnLegislations.aspx",
        },
        "keywords": [
            "student data", "personal data", "upload student",
            "student records", "children's data", "child data",
            "share with third party", "third-party ai",
        ],
        "guidance": "Any processing of student personal data must follow data-minimization, purpose-limitation and "
                    "consent principles. Verify parental consent for under-18s and a data-processing agreement with the vendor.",
    },
    {
        "id": "R4-kg-age-appropriate",
        "severity": "NEEDS_REVIEW",
        "title": "AI activities for KG / early years must be age-appropriate and supervised",
        "policy_basis": {
            "doc_id": "uae-moe-ai-curriculum-2025",
            "title": "UAE MoE AI curriculum (2025-2026): KG uses visual/interactive activities through stories and play",
            "source_url": "https://www.moe.gov.ae/",
        },
        "keywords": ["kindergarten", "kg ", "kg,", "early years", "age 4", "age 5", "5-year-old"],
        "guidance": "Per the UAE MoE curriculum, KG learners discover AI through visual, interactive activities, stories and play, "
                    "with designated teachers. Unsupervised or text-heavy AI use with young children needs review.",
    },
    {
        "id": "R5-teacher-ai-literacy",
        "severity": "NEEDS_REVIEW",
        "title": "Teachers deploying AI need sufficient AI literacy",
        "policy_basis": {
            "doc_id": "eu-ai-act-education-full",
            "title": "EU AI Act Article 4 (AI literacy duty for deployers)",
            "source_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        },
        "keywords": ["deploy ai", "deploy a new ai", "roll out", "introduce ai", "new ai tool",
                     "new ai tutoring system", "ai system in class", "ai system in all classrooms"],
        # Fire only when deployment is described WITHOUT any mention of training/literacy.
        "requires_absence": ["training", "literate", "literacy", "trained", "workshop", "certified"],
        "guidance": "Deployers of AI systems must ensure staff have sufficient AI literacy for the context of use "
                    "(EU AI Act Art. 4). Confirm the teacher completed AI-literacy training before classroom deployment.",
    },
    {
        "id": "R6-prohibited-exam-surveillance",
        "severity": "NON_COMPLIANT",
        "title": "No AI-only proctoring decisions without human review",
        "policy_basis": {
            "doc_id": "eu-ai-act-education-full",
            "title": "EU AI Act Annex III, point 3(d): monitoring/detecting prohibited behaviour during tests is high-risk",
            "source_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        },
        "keywords": [
            "auto-flag cheating", "automatically disqualify", "ai proctor",
            "auto disqualify", "cheating detection without review",
        ],
        "guidance": "AI monitoring of prohibited behaviour during tests is high-risk (Annex III, 3(d)). "
                    "Flags must be reviewed by a human; automatic disqualification is not permitted.",
    },
    {
        "id": "R7-child-safety",
        "severity": "NON_COMPLIANT",
        "title": "Zero tolerance: sexual content, abuse, or exploitation involving minors",
        "policy_basis": {
            "doc_id": "uae-tdra-digital-safety",
            "title": "UAE Federal Decree-Law No. 26 of 2025 (Child Digital Safety); ITU Child Online Protection",
            "source_url": "https://www.tdra.gov.ae/",
        },
        "keywords": [
            # Sexual acts and content
            "sexual content", "sexual activity", "sexual act", "sexual acts",
            "perform sex", "perform intercourse", "have sex", "having sex",
            "sex with", "sexual intercourse", "intercourse",
            "sexually", "sexualized", "sexualise", "sexualize",
            "pornographic", "pornography", "porn",
            "explicit content", "sexually explicit",
            "erotic", "molest", "molestation", "molesting",
            # Nudity
            "naked", "nude", "nudity", "undress", "undressed", "undressing",
            "strip", "stripping", "nude photos", "sexual images",
            "remove clothes", "take off clothes", "without clothes",
            # Abuse and exploitation
            "child abuse", "sexual abuse", "sex abuse",
            "abuse children", "abuse students", "abusing",
            "exploit children", "exploiting students", "exploitation",
            "grooming", "groom",
            "inappropriate touching", "inappropriately touch",
            "touch inappropriately", "unwanted touching",
            "predator", "predatory",
            # Solicitation
            "asking students to be naked", "asking to perform",
            "solicit", "soliciting", "solicitation",
        ],
        "guidance": "Any sexual content, abuse, or exploitation involving minors/students is "
                    "strictly prohibited under UAE Child Digital Safety Law and ITU Child Online "
                    "Protection guidelines. This submission must be escalated to school safeguarding "
                    "authorities immediately. EduGuard refuses to mark such content compliant.",
    },
    {
        "id": "R8-ai-hallucination-risk",
        "severity": "NEEDS_REVIEW",
        "title": "AI-generated educational content must be fact-checked before classroom use",
        "policy_basis": {
            "doc_id": "unesco-genai-guidance-2023",
            "title": "UNESCO Guidance for Generative AI in Education and Research (2023): validate AI outputs; do not treat hallucinations as fact",
            "source_url": "https://www.unesco.org/en/digital-education/generative-ai",
        },
        "keywords": [
            "ai generates lesson content without fact-checking",
            "ai-generated content without fact-check",
            "ai writes the curriculum without verification",
            "ai creates exam questions without review",
            "students rely on ai answers without verification",
            "ai chatbot answers without teacher checking",
            "ai tutor gives unverified answers",
            "ai generates learning materials without validation",
            "ai-generated homework answers without checking",
            "let ai write essays without checking",
            "ai summarizes textbooks without verification",
            "trust ai output blindly",
            "ai-generated notes without review",
            "present ai output as fact without verification",
        ],
        # Suppressed when the same sentence affirmatively describes verification
        # of AI output. (Phrased affirmatively so they cannot appear inside the
        # "without X" violation keywords above.)
        "requires_absence": ["fact-checks", "fact-checked", "verified",
                             "teacher reviews", "reviewed", "validated"],
        "guidance": "Generative AI systems hallucinate; UNESCO guidance requires that AI-generated educational "
                    "content be validated before classroom use. Confirm a teacher fact-checks AI outputs before "
                    "students rely on them.",
    },
    {
        "id": "R9-age-inappropriate-ai-tools",
        "severity": "NEEDS_REVIEW",
        "title": "AI tools for adults must not be used with young children without age verification",
        "policy_basis": {
            "doc_id": "uae-tdra-digital-safety",
            "title": "UNESCO GenAI guidance age-13 recommendation; UAE Federal Decree-Law No. 26 of 2025 (Child Digital Safety) under-13 protections",
            "source_url": "https://www.tdra.gov.ae/",
        },
        "keywords": [
            "adult ai tools with young children",
            "young children using adult ai",
            "children under 13 using generative ai",
            "under-13 using generative ai",
            "ai chatbot for 8-year-olds",
            "generative ai for 10-year-olds",
            "kids use chatgpt unsupervised",
            "elementary students on adult ai platforms",
            "no age verification",
            "without age verification",
            "ai companion for primary school children",
            "open ai chatbot for young kids",
            "adult chatbot with primary students",
            "unrestricted ai access for young children",
        ],
        # Suppressed when age gating or parental consent is affirmatively described
        # in the same sentence. (Phrased affirmatively so they cannot appear inside
        # the "no/without X" violation keywords above.)
        "requires_absence": ["with age verification", "age verification in place",
                             "age-verified", "with parental consent",
                             "age gating in place", "age-appropriate version",
                             "age restriction in place"],
        "guidance": "UNESCO recommends a minimum age of 13 for generative AI tools, and UAE child digital safety "
                    "law restricts under-13 data processing. Confirm age verification or an age-appropriate, "
                    "supervised version before deploying adult AI tools with young children.",
    },
    {
        "id": "R10-no-unreviewed-high-stakes-decisions",
        "severity": "NON_COMPLIANT",
        "title": "AI must not solely make disciplinary, admissions, or special-needs decisions",
        "policy_basis": {
            "doc_id": "eu-ai-act-education-full",
            "title": "EU AI Act (Regulation (EU) 2024/1689), Annex III: access to education and evaluation are high-risk; human oversight required",
            "source_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        },
        "keywords": [
            "ai decides disciplinary action",
            "ai determines suspension",
            "ai expels students",
            "automatic expulsion",
            "ai decides admissions",
            "ai screens applicants without human review",
            "ai determines special needs placement",
            "ai diagnoses learning disabilities",
            "ai decides special education eligibility",
            "automated disciplinary decisions",
            "ai recommends expulsion without review",
            "ai alone decides student dismissal",
            "algorithmic admissions decisions",
            "ai flags students for discipline without review",
            "ai determines exclusion from school",
        ],
        "guidance": "Disciplinary, admissions, and special-needs determinations are high-stakes decisions affecting "
                    "access to education (EU AI Act Annex III high-risk). AI may assist, but a human must make or "
                    "meaningfully review the final decision.",
    },
]


class ComplianceChecker:
    def __init__(self, rules=None):
        self.rules = rules or RULES

    def evaluate(self, lesson_plan, context=""):
        """Returns (verdict, fired_rules). Pure function of the inputs."""
        text = f"{lesson_plan}\n{context}".lower()
        sentences = [s.strip() for s in text.replace(";", ".").split(".")]
        negations = ("not ", "without ", "never ", "doesn't ", "don't ",
                     "isn't ", "aren't ", "won't ", "cannot ", "can't ", "no ",
                     "banned ", "ban ", "prohibit ", "prohibits ", "prohibited ",
                     "forbid ", "forbidden ", "against ")
        fired = []
        for rule in self.rules:
            matched = []
            matched_sentences = []
            for kw in rule["keywords"]:
                # Word-boundary regex: avoids matching "trained" inside "untrained"
                kw_pattern = r"\b" + re.escape(kw) + r"\b"
                for sent in sentences:
                    m = re.search(kw_pattern, sent)
                    if not m:
                        continue
                    # Negated only if a negation word appears BEFORE the keyword.
                    before = f" {sent[:m.start()]} "
                    if not any(neg in before for neg in negations):
                        matched.append(kw)
                        matched_sentences.append(sent)
                        break
            if not matched:
                continue
            # requires_absence: skip if any "already handled" phrase is present
            # as a whole word (fixes "untrained" matching "trained"), but only
            # within the sentences that actually matched this rule, so an
            # unrelated "training" mention elsewhere cannot silence the rule.
            absent = rule.get("requires_absence", [])
            if absent and any(
                re.search(r"\b" + re.escape(phrase) + r"\b", sent)
                for sent in matched_sentences
                for phrase in absent
            ):
                continue
            fired.append({
                    "rule_id": rule["id"],
                    "severity": rule["severity"],
                    "title": rule["title"],
                    "matched_keywords": matched,
                    "guidance": rule["guidance"],
                    "policy_basis": rule["policy_basis"],
                })
        verdict = "COMPLIANT"
        for fr in fired:
            if fr["severity"] == "NON_COMPLIANT":
                verdict = "NON_COMPLIANT"
                break
            if fr["severity"] == "NEEDS_REVIEW":
                verdict = "NEEDS_REVIEW"
        return verdict, fired
