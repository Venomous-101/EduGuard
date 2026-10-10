"""ChromaDB knowledge-base store for EduGuard UAE.

Every chunk carries mandatory citation metadata: doc_id, title, source_url.
Retrieval returns verbatim chunk text plus that metadata, so every downstream
claim can be traced to a source document. No chunk without a source URL is
ever ingested.

Embeddings: ChromaDB's built-in ONNX embedding (all-MiniLM-L6-v2), fully
local, no API key. Set EDUGUARD_EMBEDDING=sentence-transformers to use the
heavier torch-based model instead (requires `pip install sentence-transformers`).
"""
import os

import chromadb
from chromadb.utils import embedding_functions
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

COLLECTION_NAME = "eduguard_policy_kb"


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
        """Returns list of dicts: text, doc_id, title, source_url, chunk_id, distance."""
        try:
            collection = self.client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=_make_embedding_function(),
            )
        except Exception:
            collection = self.collection
        res = collection.query(
            query_texts=[query_text], n_results=n_results
        )
        hits = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            hits.append({
                "text": doc,
                "doc_id": meta.get("doc_id"),
                "title": meta.get("title"),
                "source_url": meta.get("source_url"),
                "chunk_id": meta.get("chunk_id"),
                "distance": dist,
            })
        return hits

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
