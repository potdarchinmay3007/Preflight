"""Policy search for Preflight.

Splits the policy files into small chunks, stores them in ChromaDB, and finds
the chunk that best answers a question.

Build the index once (and again whenever policy/ changes):
    python rag.py

Do not print anything at import time: over stdio, stdout carries the MCP protocol.
"""
from pathlib import Path

import chromadb

POLICY_DIR = Path(__file__).parent / "policy"
INDEX_DIR = Path(__file__).parent / "data" / "chroma"

CHUNK_WORDS = 120    # words per chunk
CHUNK_OVERLAP = 20   # words shared between neighbouring chunks
TOP_K = 1            # chunks returned per question

# Count tokens with tiktoken if it works, otherwise estimate from word count.
try:
    import tiktoken
    _encoder = tiktoken.get_encoding("cl100k_base")
    TOKEN_METHOD = "tiktoken cl100k_base"

    def count_tokens(text):
        return len(_encoder.encode(text))
except Exception:
    TOKEN_METHOD = "words x 1.3 (estimate)"

    def count_tokens(text):
        return round(len(text.split()) * 1.3)


def split_words(text):
    """Cut text into chunks of CHUNK_WORDS words, overlapping by CHUNK_OVERLAP."""
    words = text.split()
    step = CHUNK_WORDS - CHUNK_OVERLAP
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + CHUNK_WORDS]))
        if start + CHUNK_WORDS >= len(words):
            break
    return chunks


def read_policies():
    """Return {file name: text} for every .md file in policy/."""
    files = sorted(POLICY_DIR.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No .md files found in {POLICY_DIR}")
    return {f.name: f.read_text(encoding="utf-8") for f in files}


def get_client():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(INDEX_DIR))


def build_index():
    """Rebuild the search index from the policy files. Returns the chunk count."""
    client = get_client()
    try:
        client.delete_collection("policy")
    except Exception:
        pass  # nothing to delete on the first run
    collection = client.create_collection("policy", metadata={"hnsw:space": "cosine"})

    ids, texts, sources = [], [], []
    for name, text in read_policies().items():
        for i, chunk in enumerate(split_words(text)):
            ids.append(f"{name}#{i}")
            texts.append(chunk)
            sources.append({"source": name})

    collection.add(ids=ids, documents=texts, metadatas=sources)
    return len(ids)


def search_policy(questions):
    """Find the best policy chunk for each question, plus token counts."""
    try:
        collection = get_client().get_collection("policy")
    except Exception:
        raise RuntimeError("Policy index not found. Run: python rag.py")

    results = collection.query(query_texts=questions, n_results=TOP_K)

    chunks = []
    seen = set()
    for q, question in enumerate(questions):
        for i, chunk_id in enumerate(results["ids"][q]):
            if chunk_id in seen:  # two questions can find the same chunk
                continue
            seen.add(chunk_id)
            chunks.append({
                "source": results["metadatas"][q][i]["source"],
                "text": results["documents"][q][i],
                "question": question,
                "distance": round(results["distances"][q][i], 4),
            })

    all_docs = read_policies().values()
    return {
        "chunks": chunks,
        "chunks_returned": len(chunks),
        "tokens_returned": sum(count_tokens(c["text"]) for c in chunks),
        "tokens_all_policy_docs": sum(count_tokens(t) for t in all_docs),
        "token_method": TOKEN_METHOD,
    }


if __name__ == "__main__":
    total = build_index()
    print(f"Indexed {total} chunks from {POLICY_DIR}")
