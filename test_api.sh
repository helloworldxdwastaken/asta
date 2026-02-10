#!/bin/bash
# Quick API smoke tests for Asta backend (expect backend at http://localhost:8000)
set -e
BASE="${1:-http://localhost:8000/api}"
echo "Testing base: $BASE"
echo ""

test_ok() {
  local name="$1"
  local method="${2:-GET}"
  local path="$3"
  local data="$4"
  local code
  if [ -n "$data" ]; then
    code=$(curl -s -o /tmp/asta_test_out.json -w "%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$BASE$path")
  else
    code=$(curl -s -o /tmp/asta_test_out.json -w "%{http_code}" -X "$method" "$BASE$path")
  fi
  if [ "$code" = "200" ] || [ "$code" = "201" ] || [ "$code" = "202" ]; then
    echo "  OK $name ($code)"
  else
    echo "  FAIL $name (HTTP $code)"
    cat /tmp/asta_test_out.json | head -3
    return 1
  fi
}

echo "=== Health ==="
test_ok "GET /health" GET "/health" || true
curl -s "$BASE/health" | head -1
echo ""

echo "=== Status ==="
test_ok "GET /status" GET "/status"
echo ""

echo "=== Settings / providers ==="
test_ok "GET /providers" GET "/providers"
test_ok "GET /settings/default-ai" GET "/settings/default-ai"
test_ok "GET /settings/keys" GET "/settings/keys"
test_ok "GET /settings/models" GET "/settings/models"
test_ok "GET /settings/skills" GET "/settings/skills"
echo ""

echo "=== Files ==="
test_ok "GET /files/list" GET "/files/list"
echo ""

echo "=== Drive ==="
test_ok "GET /drive/status" GET "/drive/status"
test_ok "GET /drive/list" GET "/drive/list"
echo ""

echo "=== RAG / Learning ==="
test_ok "GET /rag/learned" GET "/rag/learned"
echo ""

echo "=== Spotify ==="
test_ok "GET /spotify/status" GET "/spotify/status"
test_ok "GET /spotify/setup" GET "/spotify/setup"
echo ""

echo "=== Chat (POST) ==="
test_ok "POST /chat" POST "/chat" '{"text":"Hi","provider":"default","user_id":"default"}' || true
echo ""

echo "=== Notifications ==="
test_ok "GET /notifications" GET "/notifications"
echo ""

echo "=== WhatsApp QR ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/whatsapp/qr")
if [ "$code" = "200" ]; then echo "  OK GET /whatsapp/qr (200)"; else echo "  FAIL /whatsapp/qr ($code)"; fi
echo ""

echo "Done."
