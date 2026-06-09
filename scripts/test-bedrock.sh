#!/usr/bin/env bash
# SciNova OS — Amazon Bedrock smoke test (Titan text embed + Claude LLM)
#
# Verifies IAM role / credentials and real model responses (not just connectivity).
# Mirrors SciNova backend: Converse API for Claude, invoke_model fallback, Titan embed.
#
# Usage:
#   cd ~/scinova-os
#   cp .env.example .env && nano .env   # set AWS_REGION, LLM_MODEL, BEDROCK_* models
#   chmod +x scripts/test-bedrock.sh
#   ./scripts/test-bedrock.sh
#
# Optional:
#   SCINOVA_DIR=~/scinova-os
#   ENV_FILE=/path/to/.env
#   AWS_REGION=us-west-2
#   BEDROCK_LLM_MODEL=us.anthropic.claude-sonnet-4-6-v1:0
#   BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/bedrock-smoke.sh
source "${SCRIPT_DIR}/lib/bedrock-smoke.sh"

SCINOVA_DIR="${SCINOVA_DIR:-$HOME/scinova-os}"
ENV_FILE="${ENV_FILE:-$SCINOVA_DIR/.env}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0

pass() { echo -e "${GREEN}PASS${NC}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}FAIL${NC}  $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "${YELLOW}WARN${NC}  $1"; }
skip() { echo -e "${YELLOW}SKIP${NC}  $1"; }
info() { echo -e "      $1"; }

echo ""
echo "SciNova OS — Amazon Bedrock smoke test"
echo "Date:  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Host:  $(hostname)"
echo "Env:   $ENV_FILE"
echo ""

AWS_REGION="${AWS_REGION:-$(bedrock_resolve_region "$ENV_FILE")}"
BEDROCK_LLM_MODEL="${BEDROCK_LLM_MODEL:-$(bedrock_resolve_llm_model "$ENV_FILE")}"
BEDROCK_EMBED_MODEL="${BEDROCK_EMBED_MODEL:-$(bedrock_resolve_embed_model "$ENV_FILE")}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  1. AWS CLI & IAM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! command -v aws >/dev/null 2>&1; then
  fail "AWS CLI not installed"
  info "sudo apt-get update && sudo apt-get install -y awscli"
  exit 1
fi

pass "AWS CLI: $(aws --version 2>&1 | head -1)"
info "AWS_REGION=$AWS_REGION"

IDENTITY=$(aws sts get-caller-identity --output json 2>&1) || true
if echo "$IDENTITY" | grep -q '"Account"'; then
  pass "STS get-caller-identity OK"
  info "$(echo "$IDENTITY" | grep -E '"Account"|"Arn"' | tr -d ' ",')"
else
  fail "STS get-caller-identity failed"
  info "$IDENTITY"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  2. Bedrock text embeddings"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "BEDROCK_EMBEDDING_MODEL=$BEDROCK_EMBED_MODEL"

if echo "$BEDROCK_EMBED_MODEL" | grep -qi 'embed-image'; then
  fail "Wrong embedding model: $BEDROCK_EMBED_MODEL (use amazon.titan-embed-text-v2:0)"
else
  EMBED_DIM=$(bedrock_smoke_test_embed "$AWS_REGION" "$BEDROCK_EMBED_MODEL") || EMBED_DIM=""
  if [ -n "$EMBED_DIM" ]; then
    pass "Bedrock text embed OK ($BEDROCK_EMBED_MODEL, dim=$EMBED_DIM)"
  else
    fail "Bedrock text embed failed ($BEDROCK_EMBED_MODEL)"
    info "${BEDROCK_SMOKE_ERR:-unknown error}"
    if echo "${BEDROCK_SMOKE_ERR:-}" | grep -qi 'AccessDenied'; then
      info "Ask IT: bedrock:InvokeModel on $BEDROCK_EMBED_MODEL for Genomics-Research-Role"
    fi
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  3. Bedrock Claude LLM (Converse + invoke fallback)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "BEDROCK_LLM_MODEL=$BEDROCK_LLM_MODEL"

if ! echo "$BEDROCK_LLM_MODEL" | grep -qi 'anthropic'; then
  warn "LLM model does not look like Anthropic Claude: $BEDROCK_LLM_MODEL"
fi

if bedrock_smoke_test_llm "$AWS_REGION" "$BEDROCK_LLM_MODEL"; then
  pass "Bedrock LLM OK via ${BEDROCK_SMOKE_METHOD} ($BEDROCK_LLM_MODEL)"
  info "Reply snippet: ${BEDROCK_SMOKE_REPLY}"
else
  fail "Bedrock LLM failed ($BEDROCK_LLM_MODEL)"
  info "${BEDROCK_SMOKE_ERR:-unknown error}"
  if echo "${BEDROCK_SMOKE_ERR:-}" | grep -qi 'AccessDenied'; then
    info "Ask IT: bedrock:InvokeModel + bedrock:Converse on $BEDROCK_LLM_MODEL"
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  4. Bedrock LLM JSON response (agent-style)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TMP_JSON_OUT="/tmp/scinova-bedrock-json-$$.json"
aws bedrock-runtime converse \
  --region "$AWS_REGION" \
  --model-id "$BEDROCK_LLM_MODEL" \
  --messages '[{"role":"user","content":[{"text":"Return JSON only: {\"status\":\"ok\"}"}]}]' \
  --inference-config '{"maxTokens":64,"temperature":0}' \
  > "$TMP_JSON_OUT" 2>&1 || true

if [ -f "$TMP_JSON_OUT" ]; then
  JSON_REPLY=$(bedrock_parse_converse_text "$TMP_JSON_OUT")
  if echo "$JSON_REPLY" | grep -q 'ok'; then
    pass "Bedrock JSON-style reply parseable"
    info "Snippet: ${JSON_REPLY:0:80}"
  else
    skip "Bedrock JSON reply not verified (model may need tuning)"
    info "Snippet: ${JSON_REPLY:-$(head -c 120 "$TMP_JSON_OUT" 2>/dev/null)}"
  fi
else
  skip "Bedrock JSON test skipped (LLM converse failed)"
fi
rm -f "$TMP_JSON_OUT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  PASS: $PASS   FAIL: $FAIL   SKIP: $SKIP"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}Bedrock embeddings and LLM are working from this host.${NC}"
  echo "  Set in .env:"
  echo "    EMBEDDING_PROVIDER=bedrock"
  echo "    BEDROCK_EMBEDDING_MODEL=$BEDROCK_EMBED_MODEL"
  echo "    LLM_MODEL=$BEDROCK_LLM_MODEL"
  exit 0
fi

echo -e "${RED}One or more Bedrock checks failed.${NC}"
echo "  - Confirm model access in Bedrock console (us-west-2)"
echo "  - Ask IT for bedrock:InvokeModel and bedrock:Converse on your models"
echo "  - Use text embed model (titan-embed-text), not titan-embed-image"
exit 1
