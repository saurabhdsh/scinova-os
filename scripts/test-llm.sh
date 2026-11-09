#!/usr/bin/env bash
# Paste the key and endpoint, save, then run: bash scripts/test-llm.sh
KEY=""
ENDPOINT="https://api.openai.com/v1"

curl -sS "${ENDPOINT%/}/chat/completions" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with exactly: PONG"}]}'
echo
