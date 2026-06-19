# SciAi-Nova OS — shared Bedrock embed + LLM smoke tests.
# Source from preflight/test scripts:  source "$(dirname "$0")/lib/bedrock-smoke.sh"

bedrock_env_get() {
  local env_file="$1"
  local key="$2"
  local default="${3:-}"
  if [ ! -f "$env_file" ]; then
    echo "$default"
    return
  fi
  local val
  val=$(grep -E "^${key}=" "$env_file" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/\r$//')
  if [ -n "$val" ]; then
    echo "$val"
  else
    echo "$default"
  fi
}

# Resolve Claude / Anthropic Bedrock model id from .env (matches SciNova llm_service routing).
bedrock_resolve_llm_model() {
  local env_file="${1:-}"
  local llm_model bedrock_llm_model
  llm_model=$(bedrock_env_get "$env_file" "LLM_MODEL" "")
  bedrock_llm_model=$(bedrock_env_get "$env_file" "BEDROCK_LLM_MODEL" "")

  if [ -n "$bedrock_llm_model" ]; then
    echo "$bedrock_llm_model"
    return
  fi
  if echo "$llm_model" | grep -qi 'anthropic\.'; then
    echo "$llm_model"
    return
  fi
  echo "us.anthropic.claude-sonnet-4-6-v1:0"
}

bedrock_resolve_embed_model() {
  local env_file="${1:-}"
  local from_env
  from_env=$(bedrock_env_get "$env_file" "BEDROCK_EMBEDDING_MODEL" "")
  if [ -n "$from_env" ]; then
    echo "$from_env"
    return
  fi
  echo "${BEDROCK_EMBED_MODEL:-amazon.titan-embed-text-v2:0}"
}

bedrock_resolve_region() {
  local env_file="${1:-}"
  local from_env
  from_env=$(bedrock_env_get "$env_file" "AWS_REGION" "")
  if [ -n "$from_env" ]; then
    echo "$from_env"
    return
  fi
  echo "${AWS_REGION:-us-west-2}"
}

# Extract assistant text from Bedrock Converse API JSON response file.
bedrock_parse_converse_text() {
  local response_file="$1"
  python3 - "$response_file" <<'PY' 2>/dev/null || true
import json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
blocks = data.get("output", {}).get("message", {}).get("content", [])
text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
print(text.strip()[:120])
PY
}

# Extract assistant text from Anthropic invoke_model JSON response file.
bedrock_parse_invoke_text() {
  local response_file="$1"
  python3 - "$response_file" <<'PY' 2>/dev/null || true
import json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
parts = data.get("content") or []
text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
print(text.strip()[:120])
PY
}

# Returns 0 on success; prints dimension to stdout on embed success.
# Sets BEDROCK_SMOKE_ERR on failure.
bedrock_smoke_test_embed() {
  local region="$1"
  local model_id="$2"
  local tmp_body="/tmp/scinova-bedrock-embed-body-$$.json"
  local tmp_out="/tmp/scinova-bedrock-embed-out-$$.json"
  BEDROCK_SMOKE_ERR=""

  if echo "$model_id" | grep -qi 'embed-image'; then
    BEDROCK_SMOKE_ERR="Model $model_id is for images — use amazon.titan-embed-text-v2:0 for SciNova RAG"
    rm -f "$tmp_body" "$tmp_out"
    return 1
  fi

  printf '%s' '{"inputText":"SciNova Bedrock embedding smoke test","normalize":true}' > "$tmp_body"
  BEDROCK_SMOKE_ERR=$(aws bedrock-runtime invoke-model \
    --region "$region" \
    --model-id "$model_id" \
    --content-type application/json \
    --accept application/json \
    --body "fileb://${tmp_body}" \
    "$tmp_out" 2>&1) || true
  rm -f "$tmp_body"

  if [ -f "$tmp_out" ] && grep -q '"embedding"' "$tmp_out" 2>/dev/null; then
    python3 -c "import json; print(len(json.load(open('$tmp_out'))['embedding']))" 2>/dev/null
    rm -f "$tmp_out"
    return 0
  fi

  rm -f "$tmp_out"
  return 1
}

# Test Claude via Converse API (same path as SciNova llm_service._bedrock_chat).
# Sets BEDROCK_SMOKE_ERR and BEDROCK_SMOKE_REPLY on completion. Returns 0 on success.
bedrock_smoke_test_llm_converse() {
  local region="$1"
  local model_id="$2"
  local tmp_out="/tmp/scinova-bedrock-llm-converse-$$.json"
  BEDROCK_SMOKE_ERR=""
  BEDROCK_SMOKE_REPLY=""

  aws bedrock-runtime converse \
    --region "$region" \
    --model-id "$model_id" \
    --messages '[{"role":"user","content":[{"text":"Reply with exactly: OK"}]}]' \
    --inference-config '{"maxTokens":32,"temperature":0}' \
    > "$tmp_out" 2>&1 || true

  if [ -f "$tmp_out" ] && grep -q '"output"' "$tmp_out" 2>/dev/null; then
    BEDROCK_SMOKE_REPLY=$(bedrock_parse_converse_text "$tmp_out")
    if [ -n "$BEDROCK_SMOKE_REPLY" ]; then
      rm -f "$tmp_out"
      return 0
    fi
  fi

  if [ -f "$tmp_out" ]; then
    BEDROCK_SMOKE_ERR=$(head -c 400 "$tmp_out")
  else
    BEDROCK_SMOKE_ERR="converse produced no output"
  fi
  rm -f "$tmp_out"
  return 1
}

# Fallback: Anthropic invoke_model (SciNova llm_service._bedrock_invoke_chat).
bedrock_smoke_test_llm_invoke() {
  local region="$1"
  local model_id="$2"
  local tmp_body="/tmp/scinova-bedrock-llm-body-$$.json"
  local tmp_out="/tmp/scinova-bedrock-llm-invoke-$$.json"
  BEDROCK_SMOKE_ERR=""
  BEDROCK_SMOKE_REPLY=""

  printf '%s' '{"anthropic_version":"bedrock-2023-05-31","max_tokens":32,"temperature":0,"messages":[{"role":"user","content":"Reply with exactly: OK"}]}' > "$tmp_body"

  BEDROCK_SMOKE_ERR=$(aws bedrock-runtime invoke-model \
    --region "$region" \
    --model-id "$model_id" \
    --content-type application/json \
    --accept application/json \
    --body "fileb://${tmp_body}" \
    "$tmp_out" 2>&1) || true
  rm -f "$tmp_body"

  if [ -f "$tmp_out" ] && grep -q '"content"' "$tmp_out" 2>/dev/null; then
    BEDROCK_SMOKE_REPLY=$(bedrock_parse_invoke_text "$tmp_out")
    if [ -n "$BEDROCK_SMOKE_REPLY" ]; then
      rm -f "$tmp_out"
      return 0
    fi
  fi

  rm -f "$tmp_out"
  return 1
}

# Converse first, then invoke_model fallback (mirrors SciNova backend).
bedrock_smoke_test_llm() {
  local region="$1"
  local model_id="$2"
  if bedrock_smoke_test_llm_converse "$region" "$model_id"; then
    BEDROCK_SMOKE_METHOD="converse"
    return 0
  fi
  if bedrock_smoke_test_llm_invoke "$region" "$model_id"; then
    BEDROCK_SMOKE_METHOD="invoke_model"
    return 0
  fi
  BEDROCK_SMOKE_METHOD=""
  return 1
}
