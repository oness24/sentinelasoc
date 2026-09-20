# SentinelaSOC — imagem de producao (CPU, autocontida)
# Build: docker build -f docker/Dockerfile -t sentinelasoc .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf_cache \
    BASE_DIR=/app

WORKDIR /app

# Dependencias: torch CPU primeiro (imagem menor), depois o pacote
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir .

# Codigo de aplicacao e dados
COPY app.py ingest.py ./
COPY data ./data
COPY docs ./docs

# Indexa os documentos no build (bake do indice + cache do modelo de embeddings).
# BASE_DIR=/app faz o pacote resolver data/ e docs/ a partir do WORKDIR.
RUN python ingest.py

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/healthz')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
