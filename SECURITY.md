# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in EduGuard, please report it
responsibly. **Do not open a public GitHub issue.**

Email: aliabdullah080k@gmail.com with the subject `[EduGuard SECURITY]`.

Include:
- A description of the vulnerability
- Steps to reproduce
- The potential impact

We will acknowledge receipt within 72 hours and work on a fix. Please allow
reasonable time for remediation before any public disclosure.

## Scope

EduGuard is a hackathon demo. The following are in scope:
- The FastAPI backend (`api/`)
- The agent pipeline (`agents/`, `guardrails/`)
- The knowledge-base tooling (`kb/`)

Out of scope: the demo UI is a thin client with no auth; do not report the
absence of authentication as a vulnerability.

## Data handling

EduGuard processes **synthetic demo data only**. No real student data is
collected, stored, or transmitted. The knowledge base contains public policy
documents. API keys (if used for optional LLM backends) must never be
committed; use environment variables (see `.env.example`).

## Dependency security

- Python dependencies are version-bounded in `requirements.txt` (compatible-release floors plus upper bounds).
- Dependabot monitors for vulnerable dependencies weekly and opens PRs
  automatically (see `.github/dependabot.yml`).
- CI ingests the knowledge base and runs the full pytest suite plus smoke tests on every push and pull request (see `.github/workflows/ci.yml`).
