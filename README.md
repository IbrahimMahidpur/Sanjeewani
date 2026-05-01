# 🌿 Sanjeevani — Production Health Information System

WhatsApp + SMS medical Q&A powered by RAG + QLoRA fine-tuned LLM.

## Architecture
```
WhatsApp/SMS → Twilio Webhook → FastAPI → RAG Pipeline → LLM → Response
```

## Quick Start (Docker)
```bash
cp .env.example .env          # Fill in credentials
docker compose up -d          # Spin up all services
./scripts/ingest_kb.sh        # Ingest medical knowledge base
curl http://localhost:8000/health
```

## Services
| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI backend |
| Qdrant | 6333 | Vector DB |
| Redis | 6379 | Session cache |
| Prometheus | 9090 | Metrics |
| Grafana | 3001 | Dashboards |
| Frontend | 3000 | Admin UI |

## Channels Supported
- WhatsApp Business API (via Twilio)
- SMS (via Twilio)
- Extensible adapter pattern for Telegram, email, etc.
