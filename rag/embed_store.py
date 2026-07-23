"""
Embedding and Vector Store Persistence Module.

This module handles:
1. Generating dense vector embeddings for document chunks using the SentenceTransformer model 'all-MiniLM-L6-v2'.
2. Initializing and managing a local persistent ChromaDB collection named 'career_knowledge_base'.

Why sentence-transformers/all-MiniLM-L6-v2?
- It is a fast, lightweight, and highly effective embedding model (384-dimensional vectors).
- It runs locally without needing external API keys or cloud costs, making it ideal for offline RAG processing.
"""

import os
from typing import List, Optional
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# Default persistent directory path: /rag/chroma_db relative to workspace root
DEFAULT_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "career_knowledge_base"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_function(model_name: str = EMBEDDING_MODEL_NAME) -> HuggingFaceEmbeddings:
    """
    Initializes and returns the HuggingFaceEmbeddings model function using sentence-transformers.
    
    Args:
        model_name (str): Name of the HuggingFace model (default: 'sentence-transformers/all-MiniLM-L6-v2').
        
    Returns:
        HuggingFaceEmbeddings: The embedding function instance.
    """
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )


def get_chroma_vector_store(
    persist_directory: str = DEFAULT_PERSIST_DIR,
    collection_name: str = COLLECTION_NAME
) -> Chroma:
    """
    Returns an existing persistent Chroma vector store instance or initializes a new one.
    
    Args:
        persist_directory (str): Path to local folder where ChromaDB stores its index and database files.
        collection_name (str): Name of the Chroma collection (default: 'career_knowledge_base').
        
    Returns:
        Chroma: LangChain Chroma vector store instance.
    """
    embedding_function = get_embedding_function()
    os.makedirs(persist_directory, exist_ok=True)
    
    return Chroma(
        collection_name=collection_name,
        embedding_function=embedding_function,
        persist_directory=persist_directory
    )


def store_chunks(
    documents: List[Document],
    persist_directory: str = DEFAULT_PERSIST_DIR,
    collection_name: str = COLLECTION_NAME
) -> Chroma:
    """
    Embeds a list of Document chunks and persists them into the local ChromaDB collection.
    
    Args:
        documents (List[Document]): List of chunked Document objects.
        persist_directory (str): Directory where ChromaDB data will be saved.
        collection_name (str): Name of the vector store collection.
        
    Returns:
        Chroma: Updated Chroma vector store instance.
    """
    if not documents:
        print("[EmbedStore] No documents provided to store.")
        return get_chroma_vector_store(persist_directory=persist_directory, collection_name=collection_name)

    embedding_function = get_embedding_function()
    os.makedirs(persist_directory, exist_ok=True)

    print(f"[EmbedStore] Storing {len(documents)} chunk(s) into Chroma collection '{collection_name}' at '{persist_directory}'...")
    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embedding_function,
        collection_name=collection_name,
        persist_directory=persist_directory
    )
    
    print(f"[EmbedStore] Successfully persisted {len(documents)} chunk(s) to ChromaDB.")
    return vector_store
