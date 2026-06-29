"""
MPCI Vector Store
Handles document storage and semantic search using ChromaDB.
Uses ChromaDB's built-in embedding function for zero-dependency setup.
"""

import os
import json
from typing import List, Dict, Optional

from .business_topics import expanded_queries, section_boost

VECTOR_DIR = os.path.join(os.path.dirname(__file__), "vector_store")
CHUNKS_FILE = os.path.join(os.path.dirname(__file__), "chunks", "mpci_chunks.json")


def build_vector_store(chunks: List[Dict], persist_dir: str = VECTOR_DIR) -> Optional[object]:
    """
    Build and persist a ChromaDB vector store from chunks.
    Uses ChromaDB's default all-MiniLM-L6-v2 via ONNX runtime.
    """
    import chromadb
    from chromadb.config import Settings

    os.makedirs(persist_dir, exist_ok=True)

    print(f"Initializing ChromaDB at {persist_dir}...")
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False)
    )

    # Delete existing collection if present
    try:
        client.delete_collection("mpci_knowledge")
        print("Removed existing collection.")
    except:
        pass

    # Use ChromaDB's default embedding function (all-MiniLM-L6-v2 via ONNX)
    collection = client.create_collection(
        name="mpci_knowledge",
        metadata={"hnsw:space": "cosine"}
    )

    # Add chunks in batches
    batch_size = 32
    total = len(chunks)

    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        ids = [c["id"] for c in batch]
        texts = [c["content"] for c in batch]
        metadatas = [
            {
                "title": c["title"],
                "section_num": c.get("section_num", ""),
                "page_ref": c.get("page_ref", ""),
                "type": c.get("type", "section")
            }
            for c in batch
        ]

        collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )

        print(f"  Added {min(i + batch_size, total)}/{total} chunks...")

    print(f"Vector store built: {total} chunks in collection 'mpci_knowledge'")
    return collection


def load_vector_store(persist_dir: str = VECTOR_DIR) -> Optional[object]:
    """Load existing vector store."""
    import chromadb
    from chromadb.config import Settings

    if not os.path.exists(persist_dir):
        print(f"Vector store not found at {persist_dir}")
        return None

    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection("mpci_knowledge")
        count = collection.count()
        print(f"Loaded vector store: {count} chunks")
        return collection
    except:
        print("Collection 'mpci_knowledge' not found.")
        return None


def search_vector_store(
    collection: object,
    query: str,
    k: int = 5,
    threshold: float = 0.0
) -> List[Dict]:
    """
    Search the vector store for relevant chunks using semantic search.
    """
    merged = {}
    n_results = max(k, 8)

    for search_query in expanded_queries(query):
        results = collection.query(
            query_texts=[search_query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        if not results["documents"] or not results["documents"][0]:
            continue

        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0

            # ChromaDB returns distance; convert it to a rough similarity score.
            similarity = 1.0 / (1.0 + distance) if distance != float('inf') else 0
            section_num = metadata.get("section_num", "")
            score = similarity + section_boost(query, section_num)

            if score < threshold:
                continue

            key = f"{section_num}|{metadata.get('title', '')}"
            item = {
                "content": doc,
                "title": metadata.get("title", ""),
                "section_num": section_num,
                "page_ref": metadata.get("page_ref", ""),
                "score": score
            }
            if key not in merged or score > merged[key]["score"]:
                merged[key] = item

    return sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:k]


def get_chunks_by_sections(collection: object, section_nums: List[str]) -> List[Dict]:
    """Fetch chunks by exact section number from Chroma metadata."""
    found = []
    seen = set()

    for section_num in section_nums:
        results = collection.get(
            where={"section_num": section_num},
            include=["documents", "metadatas"]
        )

        for i, doc in enumerate(results.get("documents", [])):
            metadata = results.get("metadatas", [])[i] if results.get("metadatas") else {}
            key = f"{metadata.get('section_num', '')}|{metadata.get('title', '')}"
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "content": doc,
                "title": metadata.get("title", ""),
                "section_num": metadata.get("section_num", ""),
                "page_ref": metadata.get("page_ref", ""),
                "score": 1.0,
            })

    return found


if __name__ == "__main__":
    # Test vector store operations
    try:
        from .knowledge_base import build_knowledge_base
    except ImportError:
        from knowledge_base import build_knowledge_base

    print("Building knowledge base...")
    chunks = build_knowledge_base()
    print(f"Got {len(chunks)} chunks")

    print("\nBuilding vector store...")
    collection = build_vector_store(chunks)

    print("\nTesting search...")
    test_queries = [
        "multiple HS code declaration",
        "consignee requirements",
        "filing deadline"
    ]
    for q in test_queries:
        print(f"\nQuery: {q}")
        results = search_vector_store(collection, q, k=3)
        for r in results:
            print(f"  [{r['score']:.2f}] §{r['section_num']} {r['title']}: {r['content'][:100]}...")
