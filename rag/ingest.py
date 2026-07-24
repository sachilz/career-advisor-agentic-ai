"""
Document Ingestion Script for RAG Knowledge Base.

This script scans the '/data' directory and its subdirectories (job_descriptions, certifications, roadmaps, career_guides),
loads all supported document types (.txt, .md, .pdf), chunks them using rag/chunking.py, embeds them using
rag/embed_store.py, and persists the vector index to /rag/chroma_db.

Usage:
    python rag/ingest.py
"""

import sys
import os
import glob

# Ensure project root is in sys.path before package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader, PyPDFLoader

# Import sibling modules from rag package
from rag.chunking import chunk_documents
from rag.embed_store import store_chunks, DEFAULT_PERSIST_DIR

DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def load_documents_from_directory(data_path: str = DATA_DIR) -> List[Document]:
    """
    Recursively scans the data folder for supported files (.txt, .md, .pdf) and loads them into Document objects.
    
    Args:
        data_path (str): Path to data directory.
        
    Returns:
        List[Document]: List of raw loaded Document instances.
    """
    documents: List[Document] = []
    
    if not os.path.exists(data_path):
        print(f"[Ingest] Warning: Data path '{data_path}' does not exist.")
        return documents
        
    print(f"[Ingest] Scanning data directory: {data_path}")
    
    # Supported extensions
    supported_extensions = ["*.txt", "*.md", "*.pdf"]
    file_paths: List[str] = []
    
    for ext in supported_extensions:
        # Match files in data folder and subfolders recursively
        file_paths.extend(glob.glob(os.path.join(data_path, "**", ext), recursive=True))
        
    print(f"[Ingest] Found {len(file_paths)} document file(s) for ingestion.")
    
    for path in file_paths:
        file_name = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        
        # Skip README.md and .gitkeep files
        if file_name.lower() in ["readme.md", ".gitkeep"]:
            continue
            
        try:
            if ext in [".txt", ".md"]:
                loader = TextLoader(path, encoding="utf-8")
                loaded = loader.load()
            elif ext == ".pdf":
                loader = PyPDFLoader(path)
                loaded = loader.load()
            else:
                continue
                
            # Add relative source path to metadata for clean citation
            rel_path = os.path.relpath(path, PROJECT_ROOT)
            for doc in loaded:
                doc.metadata["source"] = rel_path
                doc.metadata["filename"] = file_name
                
            documents.extend(loaded)
            print(f"  [+] Loaded: {rel_path} ({len(loaded)} page/section)")
            
        except Exception as e:
            print(f"  [!] Error loading file '{path}': {e}")
            
    return documents


def run_ingestion(data_dir: str = DATA_DIR, persist_dir: str = DEFAULT_PERSIST_DIR):
    """
    Orchestrates full ingestion process: load -> chunk -> embed -> persist.
    
    Args:
        data_dir (str): Input directory containing source documents.
        persist_dir (str): Output directory for persistent ChromaDB storage.
    """
    print("=" * 60)
    print("Starting Knowledge Base Document Ingestion Process")
    print("=" * 60)
    
    # Step 1: Load raw documents
    raw_documents = load_documents_from_directory(data_dir)
    if not raw_documents:
        print("[Ingest] No candidate documents found to ingest. Ensure documents (.txt, .pdf, .md) are placed in /data.")
        return
        
    print(f"\n[Ingest] Total raw documents/pages loaded: {len(raw_documents)}")
    
    # Step 2: Chunk documents into ~500 token chunks
    print("[Ingest] Chunking documents (size=500, overlap=50)...")
    chunked_docs = chunk_documents(raw_documents, chunk_size=500, chunk_overlap=50)
    print(f"[Ingest] Generated {len(chunked_docs)} semantic chunk(s).")
    
    # Step 3: Embed & persist in ChromaDB
    print(f"[Ingest] Embedding chunks and persisting to '{persist_dir}'...")
    store_chunks(chunked_docs, persist_directory=persist_dir)
    
    print("=" * 60)
    print("Ingestion Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    run_ingestion()
