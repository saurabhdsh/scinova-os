#!/usr/bin/env bash
# SciAi-Nova OS — quick OpenAI + Mistral API smoke test (for AWS EC2 / any Linux host)
#
# Verifies outbound access and that your API keys work (chat + OpenAI embeddings).
#
# Usage:
#   cd ~/scinova-os
#   cp .env.example .env && nano .env    # set OPENAI_API_KEY + MISTRAL_API_KEY
#   chmod +x scripts/test-openai-mistral.sh
#   ./scripts/test-openai-mistral.sh
#
# Optional env overrides:
#   SCINOVA_DIR=~/scinova-os
#   ENV_FILE=/path/to/.env

set -u

SCINOVA_DIR="${SCINOVA_DIR:-$HOME/scinova-os}"
ENV_FILE="${ENV_FILE:-$SCINOVA_DIR/.env}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

pass() { echo -e "${GREEN}PASS${NC}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}FAIL${NC}  $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "${YELLOW}WARN${NC}  $1"; }
info() { echo -e "      $1"; }

read_env() {
  local key="$1"
  local default="${2:-}"
  if [ ! -f "$ENV_FILE" ]; then
    echo "$default"
    return
  fi
  local val
  val=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/\r$//')
  if [ -n "$val" ]; then
    echo "$val"
  else
    echo "$default"
  fi
}

http_ping() {
  local name="$1"
  local url="$2"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 "$url" 2>/dev/null || echo "000")
  case "$code" in
    200|204|301|302|401|403|421) pass "$name reachable (HTTP $code)" ;;
    000) fail "$name unreachable (timeout / firewall)" ;;
    *) warn "$name returned HTTP $code" ;;
  esac
}

api_call() {
  local url="$1"
  local auth_header="$2"
  local body="$3"
  local outfile="$4"
  curl -s -S --connect-timeout 10 --max-time 60 \
    -H "Authorization: ${auth_header}" \
    -H "Content-Type: application/json" \
    -d "$body" \
    -o "$outfile" \
    -w "%{http_code}" \
    "$url" 2>/dev/null || echo "000"
}

echo ""
echo "SciAi-Nova OS — OpenAI + Mistral API test"
echo "Date:  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Host:  $(hostname)"
echo "Env:   $ENV_FILE"
echo ""

# ── Load config ───────────────────────────────────────────────────────────────
OPENAI_API_KEY="${OPENAI_API_KEY:-$(read_env OPENAI_API_KEY)}"
OPENAI_BASE_URL="${OPENAI_BASE_URL:-$(read_env OPENAI_BASE_URL "https://api.openai.com/v1")}"
LLM_MODEL="${LLM_MODEL:-$(read_env LLM_MODEL "gpt-4o-mini")}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-$(read_env EMBEDDING_MODEL "text-embedding-3-small")}"

MISTRAL_API_KEY="${MISTRAL_API_KEY:-$(read_env MISTRAL_API_KEY)}"
MISTRAL_BASE_URL="${MISTRAL_BASE_URL:-$(read_env MISTRAL_BASE_URL "https://api.mistral.ai/v1")}"
SLM_MODEL="${SLM_MODEL:-$(read_env SLM_MODEL "ministral-8b-latest")}"

OPENAI_BASE_URL="${OPENAI_BASE_URL%/}"
MISTRAL_BASE_URL="${MISTRAL_BASE_URL%/}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  1. Outbound connectivity"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
http_ping "OpenAI host" "https://api.openai.com"
http_ping "Mistral host" "https://api.mistral.ai"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  2. OpenAI (frontier LLM + embeddings)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-your-key-here" ]; then
  fail "OPENAI_API_KEY not set in $ENV_FILE"
else
  pass "OPENAI_API_KEY present"
  info "LLM_MODEL=$LLM_MODEL"
  info "EMBEDDING_MODEL=$EMBEDDING_MODEL"

  TMP="/tmp/scinova-openai-chat-$$.json"
  CHAT_BODY=$(printf '{"model":"%s","messages":[{"role":"user","content":"Reply with exactly: OK"}],"max_tokens":10}' "$LLM_MODEL")
  CHAT_CODE=$(api_call "${OPENAI_BASE_URL}/chat/completions" "Bearer ${OPENAI_API_KEY}" "$CHAT_BODY" "$TMP")

  if [ "$CHAT_CODE" = "200" ] && grep -q '"choices"' "$TMP" 2>/dev/null; then
    REPLY=$(grep -o '"content":"[^"]*"' "$TMP" 2>/dev/null | head -1 | sed 's/"content":"//;s/"$//')
    pass "OpenAI chat/completions OK ($LLM_MODEL)"
    info "Reply snippet: ${REPLY:-<parsed>}"
  else
    fail "OpenAI chat/completions failed (HTTP $CHAT_CODE)"
    if [ -f "$TMP" ]; then
      info "$(head -c 300 "$TMP")"
    fi
  fi
  rm -f "$TMP"

  TMP="/tmp/scinova-openai-embed-$$.json"
  EMBED_BODY=$(printf '{"model":"%s","input":"SciNova AWS embedding test"}' "$EMBEDDING_MODEL")
  EMBED_CODE=$(api_call "${OPENAI_BASE_URL}/embeddings" "Bearer ${OPENAI_API_KEY}" "$EMBED_BODY" "$TMP")

  if [ "$EMBED_CODE" = "200" ] && grep -q '"embedding"' "$TMP" 2>/dev/null; then
    pass "OpenAI embeddings OK ($EMBEDDING_MODEL)"
  else
    fail "OpenAI embeddings failed (HTTP $EMBED_CODE)"
    if [ -f "$TMP" ]; then
      info "$(head -c 300 "$TMP")"
    fi
  fi
  rm -f "$TMP"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  3. Mistral (SLM)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$MISTRAL_API_KEY" ] || [ "$MISTRAL_API_KEY" = "your-mistral-api-key" ]; then
  fail "MISTRAL_API_KEY not set in $ENV_FILE"
else
  pass "MISTRAL_API_KEY present"
  info "SLM_MODEL=$SLM_MODEL"

  TMP="/tmp/scinova-mistral-chat-$$.json"
  MISTRAL_BODY=$(printf '{"model":"%s","messages":[{"role":"user","content":"Reply with exactly: OK"}],"max_tokens":10}' "$SLM_MODEL")
  MISTRAL_CODE=$(api_call "${MISTRAL_BASE_URL}/chat/completions" "Bearer ${MISTRAL_API_KEY}" "$MISTRAL_BODY" "$TMP")

  if [ "$MISTRAL_CODE" = "200" ] && grep -q '"choices"' "$TMP" 2>/dev/null; then
    REPLY=$(grep -o '"content":"[^"]*"' "$TMP" 2>/dev/null | head -1 | sed 's/"content":"//;s/"$//')
    pass "Mistral chat/completions OK ($SLM_MODEL)"
    info "Reply snippet: ${REPLY:-<parsed>}"
  else
    fail "Mistral chat/completions failed (HTTP $MISTRAL_CODE)"
    if [ -f "$TMP" ]; then
      info "$(head -c 300 "$TMP")"
    fi
  fi
  rm -f "$TMP"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  PASS: $PASS   FAIL: $FAIL"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}OpenAI and Mistral are working from this host.${NC}"
  echo "  SciNova can use OpenAI for LLM + embeddings and Mistral for SLM tasks."
  exit 0
fi

echo -e "${RED}One or more checks failed.${NC}"
echo "  - Confirm keys in .env (no quotes, no trailing spaces)"
echo "  - Ask IT to allow outbound HTTPS to api.openai.com and api.mistral.ai"
echo "  - Check billing / quota on OpenAI and Mistral consoles"
exit 1
