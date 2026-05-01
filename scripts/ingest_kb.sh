#!/bin/bash
# Ingest knowledge base into Qdrant
# Usage: ./scripts/ingest_kb.sh [path]
set -e
KB_PATH=${1:-"data/kb"}
echo "📚 Ingesting KB from $KB_PATH ..."
docker compose exec api python -m app.rag.ingestor --path "$KB_PATH"
echo "✅ Done"
