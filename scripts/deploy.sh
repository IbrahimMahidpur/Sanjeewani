#!/bin/bash
# Sanjeevani Production Deployment Script
set -e

echo "🌿 Sanjeevani Deployment"
echo "========================"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found"; exit 1; }
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || { echo "❌ Docker Compose not found"; exit 1; }

# Check .env
if [ ! -f .env ]; then
  echo "❌ .env not found. Copy .env.example and fill in credentials."
  exit 1
fi

# Source env to validate critical vars
source .env
MISSING=()
[ -z "$TWILIO_ACCOUNT_SID" ] && MISSING+=("TWILIO_ACCOUNT_SID")
[ -z "$TWILIO_AUTH_TOKEN" ]  && MISSING+=("TWILIO_AUTH_TOKEN")
[ -z "$LLM_API_KEY" ]        && MISSING+=("LLM_API_KEY")
[ -z "$TWILIO_SMS_FROM" ]    && MISSING+=("TWILIO_SMS_FROM")

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "❌ Missing required env vars: ${MISSING[*]}"
  exit 1
fi

echo "✅ Environment validated"

# Build and start
echo "🐳 Building containers..."
docker compose build --parallel

echo "🚀 Starting services..."
docker compose up -d

# Wait for API
echo "⏳ Waiting for API to be healthy..."
for i in {1..30}; do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ API is healthy"
    break
  fi
  echo "   Waiting... ($i/30)"
  sleep 3
done

# Ingest knowledge base
echo "📚 Ingesting knowledge base..."
docker compose exec api python -m app.rag.ingestor --path data/kb
echo "✅ Knowledge base ingested"

echo ""
echo "🌿 Sanjeevani is live!"
echo "   API:        http://localhost:8000"
echo "   Admin UI:   http://localhost:3000"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana:    http://localhost:3001 (admin / sanjeevani_admin)"
echo ""
echo "📱 Configure Twilio webhooks:"
echo "   WhatsApp: https://YOUR_DOMAIN/webhook/whatsapp"
echo "   SMS:      https://YOUR_DOMAIN/webhook/sms"
