# RAG Pipeline Retrieval Evaluation Log

This evaluation log tracks the semantic quality, source relevance, and precision of document chunks retrieved by the **Career Advisor Agentic AI** RAG pipeline (`all-MiniLM-L6-v2` embeddings + ChromaDB vector store).

---

## Retrieval Evaluation Table

| Query | Top Chunks Returned (Summarized) | Relevant? (Yes / No) | Notes |
| :--- | :--- | :---: | :--- |
| **1. What skills do I need to become a DevOps Engineer?** | `DevOps_Skill_Map.md` (Score: 0.6405), `DevOps_Engineer_JD.md` (Score: 0.7222) | `Yes` | High precision; retrieves Linux, CI/CD, Docker/K8s, IaC, and monitoring skill roadmaps. |
| **2. What certifications are good for cloud computing beginners?** | `Azure_vs_AWS.md` (Score: 0.6214), `AWS_Certifications_Guide.md` (Score: 0.6531) | `Yes` | Accurately identifies AWS Cloud Practitioner (CLF-C02) and Azure AZ-900 for beginners. |
| **3. What does a Data Scientist job description typically require?** | `Data_Scientist_JD.md` (Score: 0.9073), `Data_Scientist_JD.md` (Score: 0.9586) | `Yes` | Excellent accuracy; pulls Python, SQL, ML models (Scikit-Learn/TensorFlow), and EDA requirements. |
| **4. How do I prepare for a software engineering interview?** | `Software_Interview_Prep.md` (Score: 0.5408), `Software_Interview_Prep.md` (Score: 1.1162) | `Yes` | Highly relevant; covers DSA (LeetCode), System Design, and STAR behavioral interview method. |
| **5. What's the difference between AWS and Azure certifications for beginners?** | `Azure_vs_AWS.md` (Score: 0.2709), `Azure_vs_AWS.md` (Score: 0.5915) | `Yes` | Exceptional match (Score 0.2709); compares market share, ecosystem fit (startups vs enterprise), and exam formats. |

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
