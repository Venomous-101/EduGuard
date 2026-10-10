"""Audit logger: every pipeline step is appended to a JSONL file with timestamps.

This is the traceability backbone of EduGuard UAE. Judges (and auditors) can
replay exactly what the agent retrieved, which rules fired, and why a verdict
was produced. Nothing is logged to the console only; everything lands here.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone


class AuditLogger:
    def __init__(self, log_dir=None, run_id=None):
        self.log_dir = log_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "audit",
        )
        os.makedirs(self.log_dir, exist_ok=True)
        self.run_id = run_id or f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.path = os.path.join(self.log_dir, f"{self.run_id}.jsonl")
        self._seq = 0

    def log(self, stage, event, data=None):
        """Append one audit event. stage: e.g. 'retrieval', 'rules', 'verdict'."""
        self._seq += 1
        record = {
            "seq": self._seq,
            "run_id": self.run_id,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "epoch": time.time(),
            "stage": stage,
            "event": event,
            "data": data or {},
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def log_retrieval(self, query, hits):
        self.log("retrieval", "kb_query", {
            "query": query,
            "num_hits": len(hits),
            "hits": [
                {
                    "doc_id": h.get("doc_id"),
                    "title": h.get("title"),
                    "source_url": h.get("source_url"),
                    "chunk_id": h.get("chunk_id"),
                    "distance": h.get("distance"),
                }
                for h in hits
            ],
        })

    def log_rule_evaluation(self, rule_id, fired, detail):
        self.log("rules", "rule_evaluated", {
            "rule_id": rule_id,
            "fired": fired,
            "detail": detail,
        })

    def log_verdict(self, verdict, citations, reasoning_summary):
        self.log("verdict", "verdict_produced", {
            "verdict": verdict,
            "num_citations": len(citations),
            "citations": citations,
            "reasoning_summary": reasoning_summary,
        })
