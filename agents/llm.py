"""Pluggable LLM backend for EduGuard UAE.

Backends:
  - "ollama" (default): local Ollama server, no API key needed.
  - "openai": OpenAI API via OPENAI_API_KEY env var.
  - "openrouter": OpenRouter API via per-request API key (user supplies their
    own free key in the UI; the key is used for that request only and never
    stored or logged).

If no backend is reachable, `available` is False and the pipeline degrades
gracefully: the deterministic ComplianceChecker and extractive RAG still run.
The LLM NEVER overrides deterministic rules.
"""
import os

import requests


class LLMBackend:
    def __init__(self, api_key=None, backend_override=None):
        # Per-request override (e.g. user's own OpenRouter key from the UI)
        if backend_override == "openrouter" and api_key:
            self.backend = "openrouter"
            self._api_key = api_key
            self.model = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
            self.available = True
            return
        self._api_key = None
        self.backend = os.environ.get("EDUGUARD_LLM_BACKEND", "ollama").lower()
        self.available = False
        self.model = None
        self._detect()

    def _detect(self):
        if self.backend == "openai":
            key = os.environ.get("OPENAI_API_KEY")
            if key:
                self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
                self.available = True
        else:  # ollama
            base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            self.model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
            self.ollama_base = base.rstrip("/")
            try:
                r = requests.get(f"{self.ollama_base}/api/tags", timeout=5)
                if r.status_code == 200:
                    self.available = True
            except Exception:
                self.available = False

    def generate(self, system_prompt, user_prompt, max_tokens=800, temperature=0.1):
        """Returns generated text, or None if no backend is available."""
        if not self.available:
            return None
        try:
            if self.backend == "openai":
                return self._openai_generate(system_prompt, user_prompt, max_tokens, temperature)
            if self.backend == "openrouter":
                return self._openrouter_generate(system_prompt, user_prompt, max_tokens, temperature)
            return self._ollama_generate(system_prompt, user_prompt, max_tokens, temperature)
        except Exception:
            return None

    def _ollama_generate(self, system_prompt, user_prompt, max_tokens, temperature):
        r = requests.post(
            f"{self.ollama_base}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

    def _openrouter_generate(self, system_prompt, user_prompt, max_tokens, temperature):
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": "https://github.com/Venomous-101/EduGuard",
                "X-Title": "EduGuard UAE",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    def _openai_generate(self, system_prompt, user_prompt, max_tokens, temperature):
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
