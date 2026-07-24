# ==============================================================================
# Multi-Stage Lightweight Dockerfile for Career Advisor Agentic AI
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Prevent Python from writing bytecode and buffer outputs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements file
COPY requirements.txt .

# Upgrade pip and install CPU-only PyTorch to reduce image size by ~2.2 GB
# (sentence-transformers pulls PyTorch; specifying CPU index prevents downloading GPU/CUDA binaries)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Final Runtime Environment
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8501

# Install runtime utilities (curl for health check) & cleanup apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code and data
COPY . /app

# Create persistent directory for ChromaDB and ensure proper permissions
RUN mkdir -p /app/rag/chroma_db && \
    useradd -m -u 10001 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to security-hardened non-root user
USER appuser

EXPOSE 8501

# Health check to ensure Streamlit server is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Launch Streamlit web application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
