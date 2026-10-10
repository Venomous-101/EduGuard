"""KB ingestion: chunk policy documents and load them into ChromaDB.

Sources live in kb/sources/ as .txt or .md files. Each file's first lines
carry a simple front-matter header:

    DOC_ID: uae-moe-ai-curriculum-2025
    TITLE: UAE Ministry of Education - AI as compulsory KG-12 subject (2025-2026)
    SOURCE_URL: https://...

Everything after the blank line following the header is chunked (sliding
window, ~400 words with 60-word overlap) and embedded locally with
sentence-transformers (no API key needed).

Usage:
    python -m kb.ingest            # ingest all files in kb/sources/
    python -m kb.ingest --reset    # wipe the collection first
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kb.store import PolicyKB  # noqa: E402

SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
CHUNK_WORDS = 400
OVERLAP_WORDS = 60


def parse_source_file(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    header, _, body = raw.partition("\n\n")
    meta = {}
    for line in header.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().upper()] = v.strip()
    doc_id = meta.get("DOC_ID") or os.path.splitext(os.path.basename(path))[0]
    title = meta.get("TITLE") or doc_id
    source_url = meta.get("SOURCE_URL", "")
    if not source_url:
        raise ValueError(f"{path}: SOURCE_URL is required in the header")
    return doc_id, title, source_url, body.strip()


def chunk_text(text, chunk_words=CHUNK_WORDS, overlap=OVERLAP_WORDS):
    words = re.findall(r"\S+", text)
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


def ingest(reset=False):
    kb = PolicyKB()
    if reset:
        kb.client.delete_collection("eduguard_policy_kb")
        kb = PolicyKB()
    files = sorted(glob.glob(os.path.join(SOURCES_DIR, "*.txt")) +
                   glob.glob(os.path.join(SOURCES_DIR, "*.md")))
    total = 0
    for path in files:
        if os.path.basename(path).startswith("_"):
            continue
        doc_id, title, source_url, body = parse_source_file(path)
        chunks = [
            {
                "text": c,
                "doc_id": doc_id,
                "title": title,
                "source_url": source_url,
                "chunk_id": f"{doc_id}::chunk-{i:03d}",
            }
            for i, c in enumerate(chunk_text(body))
        ]
        kb.add_chunks(chunks)
        total += len(chunks)
        print(f"ingested {len(chunks):3d} chunks  {doc_id}")
    print(f"TOTAL: {total} chunks, {kb.count()} in collection")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    ingest(reset=args.reset)
