"""ChromaDB knowledge-base store for EduGuard UAE.

Every chunk carries mandatory citation metadata: doc_id, title, source_url.
Retrieval returns verbatim chunk text plus that metadata, so every downstream
claim can be traced to a source document. No chunk without a source URL is
ever ingested.

Embeddings: ChromaDB's built-in ONNX embedding (all-MiniLM-L6-v2), fully
local, no API key. Set EDUGUARD_EMBEDDING=sentence-transformers to use the
heavier torch-based model instead (requires `pip install sentence-transformers`).
"""
import math
import os
import re

import chromadb
from chromadb.utils import embedding_functions
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

COLLECTION_NAME = "eduguard_policy_kb"

STOPWORDS = {
    "the", "a", "an", "in", "of", "to", "and", "for", "on", "with", "is",
    "are", "by", "as", "at", "or", "be", "from", "that", "this", "it",
    "will", "can", "may", "each", "all", "no", "not", "without", "use",
    "using", "used", "into", "their", "our", "we", "they", "has", "have",
}

# Domain-wide terms that appear across nearly all education AI policy docs.
# They still contribute a small lexical weight, but only specific concept terms
# trigger authority boosts or rescue high-distance semantic hits.
DOMAIN_STOPWORDS = STOPWORDS | {
    "ai", "artificial", "intelligence", "education", "educational",
    "school", "schools", "classroom", "class", "student", "students",
}

# Policy concept query expansion map
QUERY_EXPANSIONS = {
    "grading": ["assessment", "evaluation", "marks", "evaluating", "learning", "outcomes", "annex", "oversight", "high-risk"],
    "grade": ["assessment", "evaluation", "marks", "evaluating", "learning", "outcomes", "annex", "oversight"],
    "grades": ["assessment", "evaluation", "marks", "evaluating", "learning", "outcomes", "annex", "oversight"],
    "assessment": ["grading", "evaluation", "marks", "evaluating", "learning", "outcomes", "annex", "exams"],
    "evaluation": ["grading", "assessment", "marks", "evaluating", "learning", "outcomes", "annex"],
    "marks": ["grading", "grades", "assessment", "evaluation", "evaluating", "outcomes"],
    "exam": ["assessment", "evaluation", "tests", "proctoring", "learning", "outcomes", "annex", "cheating"],
    "exams": ["assessment", "evaluation", "tests", "proctoring", "learning", "outcomes", "annex", "cheating"],
    "proctoring": ["monitoring", "cheating", "tests", "exams", "annex", "high-risk", "oversight"],
    "review": ["oversight", "human", "verification", "checking"],
    "facial": ["biometric", "emotion", "recognition", "infer", "prohibited", "article", "surveillance", "expressions", "personal", "privacy", "rights"],
    "face": ["biometric", "emotion", "recognition", "facial", "prohibited", "article", "personal", "privacy"],
    "recognition": ["biometric", "emotion", "facial", "prohibited", "article", "identification", "personal", "privacy"],
    "cameras": ["biometric", "emotion", "facial", "monitoring", "surveillance", "prohibited", "privacy", "rights"],
    "camera": ["biometric", "emotion", "facial", "monitoring", "surveillance", "prohibited", "privacy", "rights"],
    "biometric": ["facial", "emotion", "recognition", "prohibited", "article", "personal", "data", "privacy"],
    "emotion": ["facial", "biometric", "recognition", "prohibited", "article", "infer"],
    "personal": ["protection", "privacy", "consent", "minimization", "purpose", "decree-law", "45"],
    "data": ["protection", "privacy", "consent", "minimization", "personal", "decree-law"],
    "records": ["personal", "data", "protection", "privacy", "consent", "minimization"],
    "third": ["vendor", "transfer", "consent", "protection", "sharing", "privacy", "commercial"],
    "party": ["vendor", "transfer", "consent", "protection", "sharing", "privacy"],
    "sell": ["purpose", "limitation", "commercial", "personal", "data", "protection", "consent"],
    "selling": ["purpose", "limitation", "commercial", "personal", "data", "protection", "consent"],
    "monetize": ["purpose", "limitation", "commercial", "personal", "data", "protection"],
    "kindergarten": ["kg", "kg-12", "curriculum", "age", "children", "stories", "play", "early", "compulsory", "moe", "visual", "interactive"],
    "kg": ["kindergarten", "kg-12", "curriculum", "stories", "play", "early", "moe"],
    "chatbot": ["generative", "age", "13", "children", "younger", "learners", "supervision", "chatgpt"],
    "children": ["child", "safety", "age", "protection", "minors", "unicef", "tdra", "kindergarten", "child-centred"],
    "teacher": ["teachers", "training", "literacy", "competency", "professional", "workforce", "deployers", "qualified"],
    "training": ["teacher", "teachers", "literacy", "competency", "professional", "qualified", "framework"],
    "literacy": ["training", "competency", "teacher", "teachers", "article", "deployers", "staff"],
    "curriculum": ["moe", "ministry", "kg-12", "2025-2026", "compulsory", "2025", "subject"],
    "safety": ["tdra", "protection", "child", "online", "digital", "safeguarding", "abuse", "itu", "26", "aecert", "unicef"],
    "online": ["protection", "child", "digital", "safety", "tdra", "itu", "cyber", "cop", "unicef"],
    "protection": ["safety", "tdra", "itu", "personal", "data", "privacy", "child", "unicef"],
    "competency": ["unesco", "framework", "students", "teachers", "human-centred", "progression", "aspects", "12"],
    "unesco": ["competency", "framework", "ethics", "generative", "human-centred", "recommendation"],
    "hallucination": ["validate", "verification", "fact-check", "misinformation", "outputs", "generative"],
    "disciplinary": ["access", "admission", "high-risk", "annex", "oversight", "evaluating"],
    "admissions": ["access", "admission", "educational", "institutions", "high-risk", "annex", "oversight"],
}


def tokenize(text):
    """Tokenize text into lowercase alphanumeric/hyphenated terms without stopwords."""
    return [
        t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (text or "").lower())
        if t not in STOPWORDS and len(t) > 1
    ]


def expand_query_terms(tokens):
    """Return dict mapping query + expanded policy concept tokens to weights."""
    weights = {}
    for t in tokens:
        base_w = 0.25 if t in DOMAIN_STOPWORDS else 1.0
        weights[t] = max(weights.get(t, 0.0), base_w)
        for exp in QUERY_EXPANSIONS.get(t, []):
            for et in tokenize(exp):
                exp_w = 0.15 if et in DOMAIN_STOPWORDS else 0.65
                weights[et] = max(weights.get(et, 0.0), exp_w)
    return weights


def canonical_doc_id(doc_id):
    """Normalize '-full' source pair IDs to their canonical base doc_id."""
    if not doc_id:
        return ""
    return doc_id[:-5] if doc_id.endswith("-full") else doc_id


def is_authoritative_source(doc_id):
    """UAE national/emirate sources and EU AI Act carry higher compliance authority."""
    if not doc_id:
        return False
    return doc_id.startswith(("uae-", "dubai-", "abudhabi-", "eu-ai-act"))


def deduplicate_full_pairs(scored_hits, full_doc_ids=None):
    """De-duplicate '-full' source pairs and rank distinct canonical sources first.

    When both `X` and `X-full` exist in the KB, they represent the same policy
    source. The pair is collapsed to a single canonical entry (preferring the
    `-full` document metadata/text when available, with the best score achieved
    by either half of the pair). Secondary chunks of an already-included
    document are placed after primary chunks of distinct canonical documents,
    while keeping all relevant chunks (distance < 1.2) ahead of irrelevant ones.
    """
    if full_doc_ids is None:
        full_doc_ids = {
            h["doc_id"] for h in scored_hits
            if (h.get("doc_id") or "").endswith("-full")
        }
    best_full_chunk = {}
    for h in scored_hits:
        did = h.get("doc_id")
        if did in full_doc_ids and did not in best_full_chunk:
            best_full_chunk[did] = h

    rel_primary = []
    rel_secondary = []
    irrel_primary = []
    irrel_secondary = []
    seen_canonical = {}
    for h in scored_hits:
        did = h.get("doc_id") or ""
        can_id = canonical_doc_id(did)
        full_twin = f"{can_id}-full"
        if can_id not in seen_canonical:
            if (
                full_twin in best_full_chunk
                and did != full_twin
                and (best_full_chunk[full_twin].get("distance", 2.0) < 1.2 or h.get("distance", 2.0) >= 1.2)
            ):
                rep = dict(best_full_chunk[full_twin])
                rep["distance"] = min(h["distance"], rep["distance"])
                seen_canonical[can_id] = full_twin
                target_hit = rep
            else:
                seen_canonical[can_id] = did
                target_hit = h
            if target_hit.get("distance", 2.0) < 1.2:
                rel_primary.append(target_hit)
            else:
                irrel_primary.append(target_hit)
        elif seen_canonical[can_id] == did and all(
            p.get("chunk_id") != h.get("chunk_id") for p in rel_primary + irrel_primary
        ):
            if h.get("distance", 2.0) < 1.2:
                rel_secondary.append(h)
            else:
                irrel_secondary.append(h)
    return rel_primary + rel_secondary + irrel_primary + irrel_secondary


def get_chroma_path():
    return os.environ.get(
        "CHROMA_DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db"),
    )


_EMBEDDING_FUNCTION_CACHE = {}


def _make_embedding_function():
    """Return the embedding function, cached per mode. Building the ONNX
    embedding function loads a model, so it is created once per process
    instead of once per query."""
    mode = os.environ.get("EDUGUARD_EMBEDDING", "onnx")
    if mode not in _EMBEDDING_FUNCTION_CACHE:
        if mode == "sentence-transformers":
            _EMBEDDING_FUNCTION_CACHE[mode] = (
                embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            )
        else:
            # Force CPU execution provider: ChromaDB's default ONNX embedding
            # tries AzureExecutionProvider first, which fails on machines
            # without it. Instantiating with CPUExecutionProvider avoids it.
            _EMBEDDING_FUNCTION_CACHE[mode] = ONNXMiniLM_L6_V2(
                preferred_providers=["CPUExecutionProvider"]
            )
    return _EMBEDDING_FUNCTION_CACHE[mode]


class PolicyKB:
    def __init__(self, persist_path=None):
        self.persist_path = persist_path or get_chroma_path()
        os.makedirs(self.persist_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_path)
        # get_or_create: on create, attach our embedding function; on load,
        # reuse the persisted one to avoid embedding-function conflicts.
        try:
            self.collection = self.client.get_collection(name=COLLECTION_NAME)
        except Exception:
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=_make_embedding_function(),
                metadata={"description": "EduGuard UAE policy knowledge base"},
            )

    def add_chunks(self, chunks):
        """chunks: list of dicts with keys: text, doc_id, title, source_url, chunk_id."""
        for c in chunks:
            if not c.get("source_url"):
                raise ValueError(f"Chunk missing source_url: {c.get('chunk_id')}")
        # Ensure the embedding function is attached for writes.
        try:
            collection = self.client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=_make_embedding_function(),
            )
        except Exception:
            collection = self.collection
        ids = [c["chunk_id"] for c in chunks]
        collection.add(
            ids=ids,
            documents=[c["text"] for c in chunks],
            metadatas=[
                {
                    "doc_id": c["doc_id"],
                    "title": c["title"],
                    "source_url": c["source_url"],
                    "chunk_id": c["chunk_id"],
                }
                for c in chunks
            ],
        )
        return len(ids)

    def query(self, query_text, n_results=5):
        """Hybrid retrieval combining semantic distance, BM25 lexical scoring,
        policy concept query expansion, UAE/EU-AI-Act authority boost, and
        de-duplication of '-full' source pairs.

        Returns list of dicts: text, doc_id, title, source_url, chunk_id, distance.
        """
        if not query_text or not query_text.strip():
            return []
        try:
            collection = self.client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=_make_embedding_function(),
            )
        except Exception:
            collection = self.collection

        all_data = collection.get(include=["documents", "metadatas"])
        all_docs = all_data.get("documents") or []
        all_metas = all_data.get("metadatas") or []
        total_chunks = len(all_docs)
        if total_chunks == 0:
            return []

        q_toks = tokenize(query_text)
        q_weights = expand_query_terms(q_toks)
        expanded_terms = [t for t, w in q_weights.items() if t not in q_toks and w >= 0.5][:10]
        sem_query = query_text if not expanded_terms else f"{query_text} {' '.join(expanded_terms)}"

        query_batch = [query_text, sem_query] if expanded_terms else [query_text]
        res_batch = collection.query(query_texts=query_batch, n_results=total_chunks)
        batch_metas = res_batch.get("metadatas", [[]])
        batch_dists = res_batch.get("distances", [[]])

        sem_map = {}
        for meta, dist in zip(batch_metas[0], batch_dists[0]):
            sem_map[meta.get("chunk_id")] = dist

        if expanded_terms and len(batch_metas) > 1:
            for meta, dist in zip(batch_metas[1], batch_dists[1]):
                cid = meta.get("chunk_id")
                raw_d = sem_map.get(cid, dist)
                sem_map[cid] = min(raw_d, 0.6 * raw_d + 0.4 * dist)

        # Build corpus token statistics for Okapi BM25
        doc_tokens = []
        df = {}
        for doc, meta in zip(all_docs, all_metas):
            header_str = f"{meta.get('title', '')} {(meta.get('doc_id') or '').replace('-', ' ')}"
            toks = tokenize(header_str) * 3 + tokenize(doc)
            doc_tokens.append(toks)
            for ut in set(toks):
                df[ut] = df.get(ut, 0) + 1

        avgdl = sum(len(t) for t in doc_tokens) / max(total_chunks, 1)
        k1, b = 1.5, 0.75

        scored = []
        for doc, meta, toks in zip(all_docs, all_metas, doc_tokens):
            cid = meta.get("chunk_id")
            doc_id = meta.get("doc_id") or ""
            raw_dist = sem_map.get(cid, 1.8)
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            dl = len(toks)
            bm25 = 0.0
            specific_matches = 0
            for qt, w in q_weights.items():
                f = tf.get(qt, 0)
                if f > 0:
                    if qt not in DOMAIN_STOPWORDS:
                        specific_matches += 1
                    n_qt = df.get(qt, 0)
                    idf = math.log(1.0 + (total_chunks - n_qt + 0.5) / (n_qt + 0.5))
                    bm25 += w * idf * (f * (k1 + 1.0)) / (f + k1 * (1.0 - b + b * dl / max(avgdl, 1.0)))

            # Preserve INSUFFICIENT_EVIDENCE behavior when query has no concept match
            if specific_matches == 0 and raw_dist >= 1.2:
                eff_dist = raw_dist
            else:
                base_dist = (
                    1.2 + 0.35 * (raw_dist - 1.2)
                    if (raw_dist > 1.2 and specific_matches >= 3)
                    else raw_dist
                )
                lex_boost = min(0.75, 0.055 * bm25)
                auth_boost = 0.07 if (specific_matches >= 2 and is_authoritative_source(doc_id)) else 0.0
                eff_dist = max(0.05, base_dist - lex_boost - auth_boost)

            scored.append({
                "text": doc,
                "doc_id": doc_id,
                "title": meta.get("title"),
                "source_url": meta.get("source_url"),
                "chunk_id": cid,
                "distance": eff_dist,
            })

        scored.sort(key=lambda h: h["distance"])
        full_ids = {m.get("doc_id") for m in all_metas if (m.get("doc_id") or "").endswith("-full")}
        deduped = deduplicate_full_pairs(scored, full_doc_ids=full_ids)
        return deduped[:n_results]

    def count(self):
        return self.collection.count()

    def list_sources(self):
        """Distinct documents currently in the KB."""
        data = self.collection.get(include=["metadatas"])
        seen = {}
        for m in data.get("metadatas", []):
            seen[m["doc_id"]] = {
                "doc_id": m["doc_id"],
                "title": m["title"],
                "source_url": m["source_url"],
            }
        return sorted(seen.values(), key=lambda s: s["doc_id"])

