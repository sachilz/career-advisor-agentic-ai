"""
Vector Store Retrieval Module.

This module provides the primary query interface for retrieving relevant domain knowledge chunks
from the persisted ChromaDB vector store ('career_knowledge_base').

Function:
    query_knowledge_base(query: str, k: int = 5) -> List[Dict[str, Any]]
"""

import os
from typing import List, Dict, Any
from rag.embed_store import get_chroma_vector_store, DEFAULT_PERSIST_DIR, COLLECTION_NAME


def query_knowledge_base(
    query: str,
    k: int = 5,
    persist_directory: str = DEFAULT_PERSIST_DIR,
    collection_name: str = COLLECTION_NAME
) -> List[Dict[str, Any]]:
    """
    Embeds a user query string and retrieves the top-k most relevant text chunks
    from the persisted ChromaDB collection.
    
    Args:
        query (str): The natural language query or question.
        k (int): Number of top relevant document chunks to return (default: 5).
        persist_directory (str): Path to persistent ChromaDB storage.
        collection_name (str): Vector database collection name.
        
    Returns:
        List[Dict[str, Any]]: List of dictionary objects formatted as:
            {
                "content": str,      # The chunk text content
                "source": str,       # The source file path or document name
                "filename": str,     # The base file name
                "score": float       # Similarity distance score (lower is closer in distance)
            }
    """
    if not query or not query.strip():
        print("[Retrieve] Warning: Received empty query string.")
        return []

    if not os.path.exists(persist_directory):
        print(f"[Retrieve] Warning: Persisted vector store directory '{persist_directory}' does not exist yet. Run ingestion first.")
        return []

    # Access persisted vector database
    vector_store = get_chroma_vector_store(
        persist_directory=persist_directory,
        collection_name=collection_name
    )

    # Perform similarity search with distance score
    results = vector_store.similarity_search_with_score(query, k=k)

    retrieved_chunks: List[Dict[str, Any]] = []

    for doc, score in results:
        source_path = doc.metadata.get("source", "Unknown Document")
        filename = doc.metadata.get("filename", os.path.basename(source_path))
        
        retrieved_chunks.append({
            "content": doc.page_content,
            "source": source_path,
            "filename": filename,
            "score": round(float(score), 4) if isinstance(score, (float, int)) else None,
            "metadata": doc.metadata
        })

    return retrieved_chunks


if __name__ == "__main__":
    # Self-test block for quick module testing
    sample_query = "What skills do I need for DevOps?"
    print(f"[Retrieve Test] Querying: '{sample_query}'")
    chunks = query_knowledge_base(sample_query, k=3)
    print(f"[Retrieve Test] Retrieved {len(chunks)} chunk(s).")
    for i, c in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} (Source: {c['source']}, Score: {c['score']}) ---")
        print(c['content'][:150] + "..." if len(c['content']) > 150 else c['content'])
