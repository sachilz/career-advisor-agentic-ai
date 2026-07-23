"""
Text Chunking Module for RAG Pipeline.

This module provides utility functions to split raw text or loaded document objects
into smaller, semantically coherent chunks using LangChain's RecursiveCharacterTextSplitter.

Why RecursiveCharacterTextSplitter?
- It attempts to split text using a hierarchical set of separators: double newlines ("\n\n"),
  single newlines ("\n"), spaces (" "), and finally character-by-character if needed.
- This approach ensures that paragraphs, sentences, and logical thoughts remain together
  within a single chunk rather than getting split arbitrarily in the middle of a word or sentence.
- A chunk size of ~500 characters/tokens with a 50 character/token overlap ensures that contextual
  information at chunk boundaries is preserved across neighboring chunks.
"""

from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def get_text_splitter(chunk_size: int = 500, chunk_overlap: int = 50) -> RecursiveCharacterTextSplitter:
    """
    Initializes and returns a RecursiveCharacterTextSplitter configured with
    the specified chunk size and chunk overlap parameters.
    
    Args:
        chunk_size (int): Target maximum number of characters/tokens per chunk (default: 500).
        chunk_overlap (int): Number of overlapping characters/tokens between adjacent chunks (default: 50).
        
    Returns:
        RecursiveCharacterTextSplitter: Configured LangChain text splitter instance.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
        separators=["\n\n", "\n", ". ", " ", ""]
    )


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """
    Splits a single raw text string into a list of smaller text chunk strings.
    
    Args:
        text (str): The raw input text string.
        chunk_size (int): Maximum size per chunk in characters (default: 500).
        chunk_overlap (int): Overlap size between chunks (default: 50).
        
    Returns:
        List[str]: List of text chunks.
    """
    if not text or not text.strip():
        return []
        
    splitter = get_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


def chunk_documents(documents: List[Document], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Document]:
    """
    Splits a list of LangChain Document objects into a list of chunked Document objects,
    preserving metadata (such as source file paths).
    
    Args:
        documents (List[Document]): List of input Document objects loaded from files.
        chunk_size (int): Target chunk size (default: 500).
        chunk_overlap (int): Overlap between chunks (default: 50).
        
    Returns:
        List[Document]: List of chunked Document objects with metadata attached.
    """
    if not documents:
        return []
        
    splitter = get_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunked_docs = splitter.split_documents(documents)
    return chunked_docs
