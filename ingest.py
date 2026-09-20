"""Reindexa os documentos de docs/ no ChromaDB.

Uso: python ingest.py          (idempotente: reconstroi a colecao do zero)
"""

from sentinelasoc.rag import ingest
from sentinelasoc.telemetry import get_logger

log = get_logger("ingest")

if __name__ == "__main__":
    total = ingest()
    log.info("Indexados %d chunks no ChromaDB.", total)
    print(f"OK: {total} chunks indexados.")
