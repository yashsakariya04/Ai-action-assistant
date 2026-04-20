# ─────────────────────────────────────────────────────────────
# Dockerfile — AI Action Assistant (Railway optimized)
#
# KEY FIXES:
#   1. Pin numpy<2 BEFORE installing torch (compatibility)
#   2. CPU-only torch (saves ~4GB vs CUDA build)
#   3. Install torch + sentence-transformers before other deps
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── STEP 1: Pin NumPy to <2 FIRST ────────────────────────────
# torch is compiled against NumPy 1.x — NumPy 2.x breaks it
RUN pip install --no-cache-dir "numpy<2"

# ── STEP 2: CPU-only PyTorch ──────────────────────────────────
# CPU wheel = ~800MB vs CUDA wheel = ~3.5GB
RUN pip install --no-cache-dir \
    torch==2.2.2 \
    --index-url https://download.pytorch.org/whl/cpu

# ── STEP 3: sentence-transformers ────────────────────────────
RUN pip install --no-cache-dir "sentence-transformers==3.0.1"

# ── STEP 4: Remaining dependencies ───────────────────────────
COPY requirements.txt .
RUN grep -v "^torch" requirements.txt \
    | grep -v "^sentence-transformers" \
    | grep -v "^numpy" \
    > requirements_slim.txt \
    && pip install --no-cache-dir -r requirements_slim.txt

# ── STEP 5: Copy project ──────────────────────────────────────
COPY . .

RUN mkdir -p /app/uploads /app/chroma_db /tmp/uploads /app/static

EXPOSE 8000

CMD ["python", "run_api.py"]