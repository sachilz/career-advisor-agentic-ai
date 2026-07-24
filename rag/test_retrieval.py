"""
Retrieval Test Script for RAG Knowledge Base.

This script executes 5 sample career queries through query_knowledge_base()
and prints the top retrieved chunks along with source metadata.

Sample Queries Evaluated:
1. What skills do I need to become a DevOps Engineer?
2. What certifications are good for cloud computing beginners?
3. What does a Data Scientist job description typically require?
4. How do I prepare for a software engineering interview?
5. What's the difference between AWS and Azure certifications for beginners?

Usage:
    python rag/test_retrieval.py
"""

import sys
import os

# Ensure project root is in Python path when executed directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rag.retrieve import query_knowledge_base


SAMPLE_QUERIES = [
    "What skills do I need to become a DevOps Engineer?",
    "What certifications are good for cloud computing beginners?",
    "What does a Data Scientist job description typically require?",
    "How do I prepare for a software engineering interview?",
    "What's the difference between AWS and Azure certifications for beginners?"
]


def run_retrieval_test(k: int = 3):
    """
    Executes sample queries against the persisted knowledge base and displays retrieved chunks.
    
    Args:
        k (int): Number of top chunks to display per query (default: 3).
    """
    print("=" * 80)
    print("RAG PIPELINE RETRIEVAL EVALUATION TEST")
    print("=" * 80)
    print(f"Total Sample Queries: {len(SAMPLE_QUERIES)}")
    print(f"Top-K Chunks per Query: {k}\n")

    for idx, query in enumerate(SAMPLE_QUERIES, 1):
        print("-" * 80)
        print(f"QUERY {idx}: \"{query}\"")
        print("-" * 80)
        
        results = query_knowledge_base(query=query, k=k)
        
        if not results:
            print("  [!] No relevant chunks returned.")
            print("      (Tip: Ensure you have placed documents in /data and executed 'python rag/ingest.py')\n")
            continue
            
        for rank, chunk in enumerate(results, 1):
            source = chunk.get("source", "Unknown Source")
            score = chunk.get("score", "N/A")
            content = chunk.get("content", "").strip()
            
            # Format snippet preview
            preview = content if len(content) <= 300 else content[:300] + "..."
            
            print(f"  Rank #{rank} | Source: {source} | Similarity Score: {score}")
            print("  " + "-" * 74)
            print(f"  {preview}")
            print()
            
    print("=" * 80)
    print("Test Completed! Record your evaluation in /rag/retrieval_evaluation.md")
    print("=" * 80)


if __name__ == "__main__":
    run_retrieval_test()
