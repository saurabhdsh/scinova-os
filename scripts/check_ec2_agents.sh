#!/usr/bin/env bash
# SciNova EC2 — validate Bedrock + agent stack (run ON the instance)
#
# Usage:
#   cd ~/scinova-os   # or ~/SciNova-OS
#   chmod +x scripts/check_ec2_agents.sh
#   ./scripts/check_ec2_agents.sh
#
# Optional:
#   ENV_FILE=/home/ec2-user/scinova-os/.env
#   AWS_REGION=us-east-1
#   BEDROCK_LLM_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/lib/bedrock-smoke.sh"

if [ -f "$HOME/scinova-os/.env" ]; then
  DEFAULT_ENV="$HOME/scinova-os/.env"
elif [ -f "$HOME/SciNova-OS/.env" ]; then
  DEFAULT_ENV="$HOME/SciNova-OS/.env"
else
  DEFAULT_ENV="$REPO_DIR/.env"
fi
ENV_FILE="${ENV_FILE:-$DEFAULT_ENV}"

AWS_REGION="${AWS_REGION:-$(bedrock_resolve_region "$ENV_FILE")}"
BEDROCK_LLM_MODEL="${BEDROCK_LLM_MODEL:-$(bedrock_resolve_llm_model "$ENV_FILE")}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
PASS=0
FAIL=0

pass() { echo -e "${GREEN}PASS${NC}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}FAIL${NC}  $1"; FAIL=$((FAIL + 1)); }
info() { echo -e "      $1"; }

echo ""
echo "SciNova EC2 agent / Bedrock check"
echo "Host:  $(hostname)"
echo "Env:   $ENV_FILE"
echo "Region $AWS_REGION"
echo "Model  $BEDROCK_LLM_MODEL"
echo ""

echo "━━━━━━━━ 1. Docker stack ━━━━━━━━"
if docker compose version >/dev/null 2>&1 || sudo docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
  docker info >/dev/null 2>&1 || DC=(sudo docker compose)
  (cd "$REPO_DIR" && "${DC[@]}" ps) || (cd "$HOME/scinova-os" && "${DC[@]}" ps) || true
  pass "docker compose available"
else
  fail "docker compose not available"
fi

echo ""
echo "━━━━━━━━ 2. Backend health ━━━━━━━━"
HEALTH=$(curl -sS -m 8 http://127.0.0.1:8000/health 2>/dev/null || true)
if echo "$HEALTH" | grep -qi 'ok\|healthy\|status'; then
  pass "backend /health: $HEALTH"
else
  # FastAPI may return {"status":"ok"} or similar
  if [ -n "$HEALTH" ]; then
    pass "backend /health responded: $HEALTH"
  else
    fail "backend /health did not respond on :8000 — is compose up?"
  fi
fi

echo ""
echo "━━━━━━━━ 3. IAM role ━━━━━━━━"
if aws sts get-caller-identity --region "$AWS_REGION" >/tmp/scinova-sts.json 2>/tmp/scinova-sts.err; then
  pass "STS OK"
  info "$(grep -E 'Account|Arn' /tmp/scinova-sts.json | tr -d ' ",' | head -4)"
else
  fail "STS failed"
  cat /tmp/scinova-sts.err
fi

echo ""
echo "━━━━━━━━ 4. Bedrock ping (short, timed) ━━━━━━━━"
START=$(date +%s)
TMP_OUT="/tmp/scinova-agent-ping-$$.json"
if aws bedrock-runtime converse \
  --region "$AWS_REGION" \
  --cli-read-timeout 60 \
  --cli-connect-timeout 10 \
  --model-id "$BEDROCK_LLM_MODEL" \
  --messages '[{"role":"user","content":[{"text":"Reply with exactly: PONG"}]}]' \
  --inference-config '{"maxTokens":32,"temperature":0}' \
  >"$TMP_OUT" 2>/tmp/scinova-agent-ping.err; then
  END=$(date +%s)
  SNIP=$(python3 -c "import json; d=json.load(open('$TMP_OUT')); print(d['output']['message']['content'][0].get('text','')[:80])" 2>/dev/null || echo "(parse failed)")
  pass "short converse in $((END - START))s — $SNIP"
else
  END=$(date +%s)
  fail "short converse failed after $((END - START))s"
  info "$(head -c 400 /tmp/scinova-agent-ping.err)"
fi
rm -f "$TMP_OUT"

echo ""
echo "━━━━━━━━ 5. Hypothesis-style JSON (timed) ━━━━━━━━"
START=$(date +%s)
TMP_OUT="/tmp/scinova-agent-json-$$.json"
python3 - <<'PY'
import json
open("/tmp/scinova-agent-json-msg.json","w").write(json.dumps([
  {"role":"user","content":[{"text":
    "Return JSON only: {\"summary\":\"ok\",\"hypotheses\":[{\"title\":\"demo\",\"statement\":\"JAK2 inhibition may reduce inflammation\",\"confidence\":0.7}],\"answer\":\"one sentence\"}"
  }]}
]))
open("/tmp/scinova-agent-json-sys.json","w").write(json.dumps([
  {"text":"You are a hypothesis builder. Respond with valid JSON only."}
]))
PY
if aws bedrock-runtime converse \
  --region "$AWS_REGION" \
  --cli-read-timeout 90 \
  --cli-connect-timeout 10 \
  --model-id "$BEDROCK_LLM_MODEL" \
  --system file:///tmp/scinova-agent-json-sys.json \
  --messages file:///tmp/scinova-agent-json-msg.json \
  --inference-config '{"maxTokens":400,"temperature":0}' \
  >"$TMP_OUT" 2>/tmp/scinova-agent-json.err; then
  END=$(date +%s)
  pass "JSON converse in $((END - START))s"
  info "$(python3 -c "import json; d=json.load(open('$TMP_OUT')); print(d['output']['message']['content'][0].get('text','')[:200])" 2>/dev/null)"
else
  END=$(date +%s)
  fail "JSON converse failed after $((END - START))s"
  info "$(head -c 500 /tmp/scinova-agent-json.err)"
fi
rm -f "$TMP_OUT" /tmp/scinova-agent-json-msg.json /tmp/scinova-agent-json-sys.json

echo ""
echo "━━━━━━━━ 6. Frontend port ━━━━━━━━"
if curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:5173 | grep -qE '200|304|302'; then
  pass "frontend :5173 responds"
else
  CODE=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:5173 2>/dev/null || echo fail)
  if [ "$CODE" != "fail" ] && [ "$CODE" != "000" ]; then
    pass "frontend :5173 HTTP $CODE"
  else
    fail "frontend :5173 not responding"
  fi
fi

echo ""
echo "Summary: PASS=$PASS FAIL=$FAIL"
echo ""
echo "If step 4 is slow (>20s) or fails: check AWS_REGION=us-east-1 and BEDROCK_MODEL_ID."
echo "If step 4 is fast but UI agents hang: git pull, then: sudo docker compose up -d --build"
echo "Watch a live agent run: sudo docker compose logs -f backend"
echo ""
exit $FAIL
