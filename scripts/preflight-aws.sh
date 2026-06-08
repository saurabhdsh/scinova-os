#!/usr/bin/env bash
# SciNova OS — AWS EC2 preflight checks
#
# Run on Genomics-Research-VM (or any Ubuntu EC2) before docker compose deploy.
#
# Usage:
#   cd ~/scinova-os          # after git clone
#   chmod +x scripts/preflight-aws.sh
#   ./scripts/preflight-aws.sh
#
# Optional env:
#   AWS_REGION=us-west-2     (default: us-west-2)
#   BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0
#   SCINOVA_DIR=~/scinova-os  (for post-deploy health checks)

set -u

AWS_REGION="${AWS_REGION:-us-west-2}"
BEDROCK_EMBED_MODEL="${BEDROCK_EMBED_MODEL:-amazon.titan-embed-text-v2:0}"
SCINOVA_DIR="${SCINOVA_DIR:-$HOME/scinova-os}"

PASS=0
WARN=0
FAIL=0
SKIP=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}FAIL${NC}  $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "${YELLOW}WARN${NC}  $1"; WARN=$((WARN + 1)); }
skip() { echo -e "${BLUE}SKIP${NC}  $1"; SKIP=$((SKIP + 1)); }
info() { echo -e "      $1"; }

section() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  $1"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

http_code() {
  local url="$1"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 "$url" 2>/dev/null || echo "000")
  echo "$code"
}

# /proc/meminfo and df -k report kilobytes (1K blocks), not bytes.
kb_to_gb() {
  awk -v kb="${1:-0}" 'BEGIN { printf "%.1f", kb/1024/1024 }'
}

echo ""
echo "SciNova OS — AWS preflight"
echo "Date:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Host:    $(hostname)"
echo "Region:  $AWS_REGION"
echo "User:    $(whoami)"

# ── 1. System resources ──────────────────────────────────────────────────────
section "1. System resources"

if [ -f /etc/os-release ]; then
  # shellcheck source=/dev/null
  . /etc/os-release
  if echo "$ID $VERSION_ID" | grep -qiE 'ubuntu (22|24)'; then
    pass "OS: $PRETTY_NAME"
  else
    warn "OS: $PRETTY_NAME (Ubuntu 22.04/24.04 recommended)"
  fi
else
  warn "OS: cannot read /etc/os-release"
fi

CPU_COUNT=$(nproc 2>/dev/null || echo 0)
if [ "$CPU_COUNT" -ge 2 ]; then
  pass "CPU cores: $CPU_COUNT (>= 2)"
else
  fail "CPU cores: $CPU_COUNT (need >= 2)"
fi

MEM_KB=$(awk '/MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
MEM_GB=$(kb_to_gb "$MEM_KB")
MEM_GB_INT=$(awk -v g="$MEM_GB" 'BEGIN { print int(g+0.5) }')
if [ "${MEM_GB_INT:-0}" -ge 8 ]; then
  pass "RAM: ${MEM_GB} GB (>= 8 GB recommended)"
elif [ "${MEM_GB_INT:-0}" -ge 4 ]; then
  warn "RAM: ${MEM_GB} GB (4 GB minimum — 8 GB recommended for full stack)"
else
  fail "RAM: ${MEM_GB} GB (need >= 4 GB)"
fi

DISK_AVAIL_KB=$(df -k / 2>/dev/null | awk 'NR==2 {print $4}')
DISK_AVAIL_GB=$(kb_to_gb "$DISK_AVAIL_KB")
DISK_AVAIL_INT=$(awk -v g="$DISK_AVAIL_GB" 'BEGIN { print int(g+0.5) }')
if [ "${DISK_AVAIL_INT:-0}" -ge 40 ]; then
  pass "Disk free on /: ${DISK_AVAIL_GB} GB (>= 40 GB)"
elif [ "${DISK_AVAIL_INT:-0}" -ge 20 ]; then
  warn "Disk free on /: ${DISK_AVAIL_GB} GB (tight — aim for 40+ GB)"
else
  fail "Disk free on /: ${DISK_AVAIL_GB} GB (need >= 20 GB)"
fi

# ── 2. EC2 metadata (public vs private) ──────────────────────────────────────
section "2. EC2 network (instance metadata)"

if curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/ >/dev/null 2>&1; then
  INSTANCE_ID=$(curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo "unknown")
  LOCAL_IP=$(curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/local-ipv4 2>/dev/null || echo "unknown")
  PUBLIC_IP=$(curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
  AZ=$(curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/placement/availability-zone 2>/dev/null || echo "unknown")

  pass "EC2 metadata reachable"
  info "Instance ID:  $INSTANCE_ID"
  info "Private IP:   $LOCAL_IP"
  info "AZ:           $AZ"

  if [ -n "$PUBLIC_IP" ]; then
    pass "Public IPv4: $PUBLIC_IP (internet-facing possible)"
    info "Partner URL options: https://YOUR-DOMAIN or http://$PUBLIC_IP:5173 (dev only)"
  else
    warn "No public IPv4 — partners likely need company VPN to reach $LOCAL_IP"
    info "Test from laptop on VPN: curl http://$LOCAL_IP:5173"
  fi
else
  skip "Not on EC2 or IMDS blocked — skipping metadata checks"
fi

# ── 3. Outbound internet ─────────────────────────────────────────────────────
section "3. Outbound connectivity"

check_url() {
  local name="$1"
  local url="$2"
  local code
  code=$(http_code "$url")
  case "$code" in
    200|204|301|302|401|403)
      pass "$name reachable (HTTP $code)"
      ;;
    000)
      fail "$name unreachable (timeout / blocked)"
      ;;
    *)
      warn "$name returned HTTP $code (may still be reachable)"
      ;;
  esac
}

check_url "General internet" "https://www.google.com"
check_url "AWS Bedrock runtime" "https://bedrock-runtime.${AWS_REGION}.amazonaws.com"
check_url "OpenAI API" "https://api.openai.com"
check_url "Mistral API" "https://api.mistral.ai"
check_url "PubMed E-utilities" "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=test&retmax=1"
check_url "KEGG REST" "https://rest.kegg.jp/list/organism"

# ── 4. AWS CLI & IAM ─────────────────────────────────────────────────────────
section "4. AWS CLI & IAM role"

if command -v aws >/dev/null 2>&1; then
  AWS_VER=$(aws --version 2>&1 | head -1)
  pass "AWS CLI installed: $AWS_VER"

  IDENTITY=$(aws sts get-caller-identity --output json 2>&1) || true
  if echo "$IDENTITY" | grep -q '"Account"'; then
    pass "STS get-caller-identity OK"
    info "$(echo "$IDENTITY" | grep -E '"Account"|"Arn"' | tr -d ' ",')"
  else
    fail "STS get-caller-identity failed"
    info "$IDENTITY"
  fi
else
  fail "AWS CLI not installed"
  info "Install: sudo apt-get update && sudo apt-get install -y awscli"
fi

# ── 5. Amazon Bedrock ────────────────────────────────────────────────────────
section "5. Amazon Bedrock ($AWS_REGION)"

if command -v aws >/dev/null 2>&1; then
  MODELS=$(aws bedrock list-foundation-models --region "$AWS_REGION" \
    --query 'modelSummaries[?contains(modelId, `titan-embed`) || contains(modelId, `claude`) || contains(modelId, `ministral`) || contains(modelId, `cohere.embed`)].modelId' \
    --output text 2>&1) || true

  if echo "$MODELS" | grep -qE 'titan-embed|claude|ministral|cohere'; then
    pass "Bedrock list-foundation-models OK"
    info "Sample models:"
    echo "$MODELS" | tr '\t' '\n' | head -8 | sed 's/^/        /'
  elif echo "$MODELS" | grep -qi 'AccessDenied'; then
    warn "Bedrock list-foundation-models denied (OK if bedrock:InvokeModel works)"
    info "Ask IT for bedrock:InvokeModel on Genomics-Research-Role"
  else
    warn "Bedrock list returned unexpected result"
    info "$MODELS"
  fi

  TMP_EMBED="/tmp/scinova-bedrock-embed-$$.json"
  TMP_BODY="/tmp/scinova-bedrock-body-$$.json"
  printf '%s' '{"inputText":"SciNova preflight test","normalize":true}' > "$TMP_BODY"
  EMBED_ERR=$(aws bedrock-runtime invoke-model \
    --region "$AWS_REGION" \
    --model-id "$BEDROCK_EMBED_MODEL" \
    --content-type application/json \
    --accept application/json \
    --body "fileb://${TMP_BODY}" \
    "$TMP_EMBED" 2>&1) || true
  rm -f "$TMP_BODY"

  if [ -f "$TMP_EMBED" ] && grep -q '"embedding"' "$TMP_EMBED" 2>/dev/null; then
    DIM=$(python3 -c "import json; print(len(json.load(open('$TMP_EMBED'))['embedding']))" 2>/dev/null || echo "?")
    pass "Bedrock embed invoke OK ($BEDROCK_EMBED_MODEL, dim=$DIM)"
    rm -f "$TMP_EMBED"
  else
    fail "Bedrock embed invoke failed ($BEDROCK_EMBED_MODEL)"
    info "$EMBED_ERR"
    if echo "$EMBED_ERR" | grep -qi 'AccessDenied'; then
      info "Ask IT: bedrock:InvokeModel on Genomics-Research-Role"
    else
      info "Enable model in Bedrock console → Model access → $AWS_REGION"
    fi
    rm -f "$TMP_EMBED"
  fi
else
  skip "Bedrock tests skipped (no AWS CLI)"
fi

# ── 6. Docker ────────────────────────────────────────────────────────────────
section "6. Docker"

if command -v docker >/dev/null 2>&1; then
  pass "Docker: $(docker --version 2>&1 | head -1)"
  if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose: $(docker compose version 2>&1 | head -1)"
  else
    fail "docker compose plugin not found"
  fi

  if groups | grep -q docker || [ "$(id -u)" -eq 0 ]; then
    pass "User can run docker (no sudo)"
  else
    warn "User not in 'docker' group — fix below, then open a NEW SSM session"
    info "sudo usermod -aG docker ubuntu && exit  # re-connect SSM as ubuntu"
  fi

  if docker info >/dev/null 2>&1; then
    pass "Docker daemon responding"
  elif sudo docker info >/dev/null 2>&1; then
    warn "Docker works with sudo only — add user to docker group and re-login"
  else
    fail "Docker daemon not running"
    info "sudo systemctl start docker && sudo systemctl enable docker"
  fi
else
  warn "Docker not installed"
  info "Install: curl -fsSL https://get.docker.com | sudo sh"
  info "         sudo usermod -aG docker \$USER  # then new SSH/SSM session"
fi

# ── 7. SciNova deploy (if already present) ───────────────────────────────────
section "7. SciNova stack (optional — if already deployed)"

if [ -d "$SCINOVA_DIR" ]; then
  pass "SciNova directory found: $SCINOVA_DIR"
  if [ -f "$SCINOVA_DIR/.env" ]; then
    pass ".env exists"
    if grep -q "scinova-dev-secret-change-in-production" "$SCINOVA_DIR/.env" 2>/dev/null; then
      warn "SECRET_KEY still default — change before production"
    fi
    if grep -q "^AWS_REGION=" "$SCINOVA_DIR/.env" 2>/dev/null; then
      info "AWS_REGION in .env: $(grep '^AWS_REGION=' "$SCINOVA_DIR/.env" | cut -d= -f2)"
    fi
  else
    warn "No .env — copy from .env.example before deploy"
  fi
else
  skip "SciNova not cloned yet at $SCINOVA_DIR"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  if [ -f "$SCINOVA_DIR/docker-compose.yml" ]; then
    RUNNING=$(cd "$SCINOVA_DIR" && docker compose ps --status running -q 2>/dev/null | wc -l | tr -d ' ')
    if [ "${RUNNING:-0}" -gt 0 ]; then
      pass "Docker compose services running: $RUNNING containers"
      cd "$SCINOVA_DIR" && docker compose ps 2>/dev/null | sed 's/^/        /'

      BACKEND_CODE=$(http_code "http://127.0.0.1:8000/health")
      FRONTEND_CODE=$(http_code "http://127.0.0.1:5173/")
      READY_CODE=$(http_code "http://127.0.0.1:8000/health/ready")

      if [ "$BACKEND_CODE" = "200" ]; then pass "Backend /health → 200"; else warn "Backend /health → $BACKEND_CODE"; fi
      if [ "$READY_CODE" = "200" ]; then pass "Backend /health/ready → 200"; else warn "Backend /health/ready → $READY_CODE"; fi
      if [ "$FRONTEND_CODE" = "200" ]; then pass "Frontend :5173 → 200"; else warn "Frontend :5173 → $FRONTEND_CODE"; fi
    else
      skip "docker compose not running — start with: cd $SCINOVA_DIR && docker compose up -d"
    fi
  fi
fi

# ── 8. Listening ports (security sanity) ─────────────────────────────────────
section "8. Listening ports (security sanity)"

if command -v ss >/dev/null 2>&1; then
  for PORT in 22 80 443 5173 8000 5432 6379; do
    if ss -tln 2>/dev/null | grep -q ":${PORT} "; then
      info "Port $PORT is listening on this host"
    fi
  done
  info "Postgres/Redis/8000 should NOT be reachable from internet (check EC2 security group)"
else
  skip "ss not available — skip port scan"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
section "Summary"

echo ""
echo "  PASS: $PASS   WARN: $WARN   FAIL: $FAIL   SKIP: $SKIP"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}Ready to deploy SciNova${NC} (resolve any WARN items for production)."
  echo ""
  echo "  Next steps:"
  echo "    git clone <repo> ~/scinova-os && cd ~/scinova-os"
  echo "    cp .env.example .env && nano .env"
  echo "    nano docker-compose.yml   # set CORS_ORIGINS to your URL"
  echo "    docker compose build && docker compose up -d"
  echo "    curl http://localhost:8000/health"
  exit 0
else
  echo -e "${RED}Fix FAIL items before deploy.${NC} WARN items are recommendations."
  echo ""
  echo "  Common fixes:"
  echo "    Bedrock AccessDenied → ask IT to add bedrock:InvokeModel to IAM role"
  echo "    No public IP         → use company VPN or ask IT for DNS + HTTPS"
  echo "    Docker missing       → curl -fsSL https://get.docker.com | sudo sh"
  exit 1
fi
