# Career Advisor Agentic AI

An intelligent agentic AI web application for Sri Lankan IT students that provides career pathing, skill gap analysis, and personalized career roadmaps built with **Streamlit**, **LangGraph**, and **ChromaDB RAG**.

---

## 🐳 Docker Setup & Running

This repository includes an optimized multi-stage `Dockerfile` and `docker-compose.yml` for lightweight container execution.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed.
- [Docker Compose](https://docs.docker.com/compose/) installed.

### 1. Environment Configuration
Copy `.env.example` to `.env` and fill in your API key credentials:
```bash
cp .env.example .env
```

### 2. Run with Docker Compose (Recommended)
Build and start the application in detached mode:
```bash
docker compose up -d --build
```
Access the application at **`http://localhost:8501`**.

To view logs:
```bash
docker compose logs -f
```

To stop the container:
```bash
docker compose down
```

---

### 3. Manual Docker Commands
If you prefer using `docker` directly:

**Build the Lightweight Image:**
```bash
docker build -t career-advisor-agentic-ai:latest .
```

**Run the Container:**
```bash
docker run -d \
  --name career_advisor_ai \
  -p 8501:8501 \
  --env-file .env \
  -v "$(pwd)/rag/chroma_db:/app/rag/chroma_db" \
  career-advisor-agentic-ai:latest
```

---

## ⚡ Lightweight Docker Optimizations Applied
- **Base Image:** `python:3.11-slim` for minimal Debian footprint.
- **CPU PyTorch Index:** Specifies `--index-url https://download.pytorch.org/whl/cpu` to avoid downloading CUDA/GPU dependencies (saves **~2.2 GB** of disk space).
- **Multi-Stage Build:** Keeps build tools outside of the final image runtime.
- **Security:** Executes container process as non-root `appuser`.

