# Knowledge Base Data Directory

This folder contains domain knowledge documents for the **Career Advisor Agentic AI** RAG pipeline.

Please place your raw knowledge base documents (`.txt`, `.pdf`, `.md`) into the appropriate subfolders below:

## Subfolders & Document Guidelines

### 1. `/job_descriptions`
- **Purpose**: Formal job descriptions and role requirements for Sri Lankan IT industry roles.
- **Accepted Files**: `.txt`, `.pdf`, `.md`
- **Examples**: `DevOps_Engineer_JD.txt`, `Data_Scientist_JD.pdf`, `Software_Engineer_JD.txt`

### 2. `/certifications`
- **Purpose**: Certification paths, exam overviews, and beginner guides for IT certifications.
- **Accepted Files**: `.txt`, `.pdf`, `.md`
- **Examples**: `AWS_Certifications_Guide.txt`, `Azure_vs_AWS.pdf`, `CompTIA_Security_Overview.txt`

### 3. `/roadmaps`
- **Purpose**: Career progression paths, skill trees, and domain roadmaps.
- **Accepted Files**: `.txt`, `.pdf`, `.md`
- **Examples**: `Frontend_Developer_Roadmap.txt`, `Backend_Career_Path.pdf`, `DevOps_Skill_Map.txt`

### 4. `/career_guides`
- **Purpose**: General career advice, interview preparation guides, resume tips, and Sri Lankan IT job market insights.
- **Accepted Files**: `.txt`, `.pdf`, `.md`
- **Examples**: `Software_Interview_Prep.txt`, `Sri_Lanka_Tech_Salary_Guide.pdf`, `Resume_Building_Tips.txt`

---

> **Note**: After placing new documents in any of these subfolders, run `python -m rag.ingest` (or `python rag/ingest.py`) to process, chunk, embed, and update the ChromaDB vector store.
