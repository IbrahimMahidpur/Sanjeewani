.PHONY: up down build logs test ingest shell

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --parallel

logs:
	docker compose logs -f api

test:
	cd backend && pip install pytest pytest-asyncio httpx -q && pytest tests/ -v

ingest:
	docker compose exec api python -m app.rag.ingestor --path data/kb

shell:
	docker compose exec api bash

query:
	@echo "Usage: make query Q='What is dengue?' TOKEN=your_token"
	curl -s -X POST http://localhost:8000/admin/test-query \
		-H "Authorization: Bearer $(TOKEN)" \
		-H "Content-Type: application/json" \
		-d '{"query":"$(Q)","channel":"whatsapp"}' | python -m json.tool

restart:
	docker compose restart api

health:
	curl -s http://localhost:8000/health | python -m json.tool

stats:
	@curl -s http://localhost:8000/admin/stats \
		-H "Authorization: Bearer $(TOKEN)" | python -m json.tool
