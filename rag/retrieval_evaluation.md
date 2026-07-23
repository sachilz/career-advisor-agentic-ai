# RAG Pipeline Retrieval Evaluation Log

This evaluation log tracks the semantic quality, source relevance, and precision of document chunks retrieved by the **Career Advisor Agentic AI** RAG pipeline (`all-MiniLM-L6-v2` embeddings + ChromaDB vector store).

---

## Retrieval Evaluation Table

| Query | Top Chunks Returned (Summarized) | Relevant? (Yes / No) | Notes |
| :--- | :--- | :---: | :--- |
| **1. What skills do I need to become a DevOps Engineer?** | *[Place summary of retrieved chunk 1 & 2 here after running `test_retrieval.py`]* | `[Pending]` | *[Notes on accuracy, missing skills, or precision]* |
| **2. What certifications are good for cloud computing beginners?** | *[Place summary of retrieved chunk 1 & 2 here after running `test_retrieval.py`]* | `[Pending]` | *[Notes on whether AWS/Azure beginner certs were covered]* |
| **3. What does a Data Scientist job description typically require?** | *[Place summary of retrieved chunk 1 & 2 here after running `test_retrieval.py`]* | `[Pending]` | *[Notes on ML frameworks, Python, SQL requirements]* |
| **4. How do I prepare for a software engineering interview?** | *[Place summary of retrieved chunk 1 & 2 here after running `test_retrieval.py`]* | `[Pending]` | *[Notes on DSA, system design, or behavioral prep]* |
| **5. What's the difference between AWS and Azure certifications for beginners?** | *[Place summary of retrieved chunk 1 & 2 here after running `test_retrieval.py`]* | `[Pending]` | *[Notes on comparative clarity between cloud vendors]* |

---

## Instructions for Evaluation
1. Add your domain documents (`.txt`, `.pdf`, `.md`) to the `/data` subfolders (`job_descriptions`, `certifications`, `roadmaps`, `career_guides`).
2. Run ingestion to create vector index:
   ```bash
   python rag/ingest.py
   ```
3. Run the retrieval test script:
   ```bash
   python rag/test_retrieval.py
   ```
4. Review the outputs printed in terminal for each of the 5 queries.
5. Fill in the **"Top Chunks Returned (Summarized)"**, **"Relevant? (Yes/No)"**, and **"Notes"** columns in the markdown table above.
