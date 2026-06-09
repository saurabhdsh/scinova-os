#!/usr/bin/env bash
# SciNova OS — Azure VM preflight checks (OpenAI + Mistral direct API)
#
# Usage:
#   cd ~/scinova-os
#   chmod +x scripts/preflight-azure.sh
#   ./scripts/preflight-azure.sh

set -u

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

kb_to_gb() {
  awk -v kb="${1:-0}" 'BEGIN { printf "%.1f", kb/1024/1024 }'
}

echo ""
echo "SciNova OS — Azure preflight"
echo "Date:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Host:    $(hostname)"
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
if [ "$CPU_COUNT" -ge 4 ]; then
  pass "CPU cores: $CPU_COUNT (>= 4)"
elif [ "$CPU_COUNT" -ge 2 ]; then
  warn "CPU cores: $CPU_COUNT (4+ recommended for full stack)"
else
  fail "CPU cores: $CPU_COUNT (need >= 2)"
fi

MEM_KB=$(awk '/MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
MEM_GB=$(kb_to_gb "$MEM_KB")
MEM_GB_INT=$(awk -v g="$MEM_GB" 'BEGIN { print int(g+0.5) }')
if [ "${MEM_GB_INT:-0}" -ge 16 ]; then
  pass "RAM: ${MEM_GB} GB (>= 16 GB recommended)"
elif [ "${MEM_GB_INT:-0}" -ge 8 ]; then
  warn "RAM: ${MEM_GB} GB (8 GB minimum — 16 GB recommended)"
else
  fail "RAM: ${MEM_GB} GB (need >= 8 GB)"
fi

DISK_AVAIL_KB=$(df -k / 2>/dev/null | awk 'NR==2 {print $4}')
DISK_AVAIL_GB=$(kb_to_gb "$DISK_AVAIL_KB")
DISK_AVAIL_INT=$(awk -v g="$DISK_AVAIL_GB" 'BEGIN { print int(g+0.5) }')
if [ "${DISK_AVAIL_INT:-0}" -ge 80 ]; then
  pass "Disk free on /: ${DISK_AVAIL_GB} GB"
elif [ "${DISK_AVAIL_INT:-0}" -ge 40 ]; then
  warn "Disk free on /: ${DISK_AVAIL_GB} GB (tight — aim for 80+ GB)"
else
  fail "Disk free on /: ${DISK_AVAIL_GB} GB (need >= 40 GB)"
fi

# ── 2. Azure metadata ────────────────────────────────────────────────────────
section "2. Azure network (instance metadata)"

PUBLIC_IP=""
if curl -s -H "Metadata:true" --connect-timeout 2 \
  "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" \
  >/tmp/scinova-azure-ip 2>/dev/null; then
  PUBLIC_IP=$(tr -d '[:space:]' < /tmp/scinova-azure-ip)
  rm -f /tmp/scinova-azure-ip
  if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "null" ]; then
    pass "Azure public IP: $PUBLIC_IP"
    info "UI URL: http://$PUBLIC_IP:5173"
    info "Set CORS_ORIGINS=http://$PUBLIC_IP:5173 in .env"
  else
    warn "No public IPv4 on this VM — use Tailscale or Cloudflare Tunnel"
  fi
else
  skip "Not on Azure or IMDS blocked"
  PUBLIC_IP=$(curl -s --connect-timeout 3 https://ifconfig.me 2>/dev/null || true)
  if [ -n "$PUBLIC_IP" ]; then
    info "Detected outbound IP (may differ from VM public IP): $PUBLIC_IP"
  fi
fi

# ── 3. Outbound connectivity ─────────────────────────────────────────────────
section "3. Outbound connectivity (LLM APIs)"

check_url() {
  local name="$1"
  local url="$2"
  local code
  code=$(http_code "$url")
  case "$code" in
    200|204|301|302|401|403|421)
      pass "$name reachable (HTTP $code)"
      ;;
    000)
      fail "$name unreachable (timeout / blocked)"
      ;;
    *)
      warn "$name returned HTTP $code (may still work with API key)"
      ;;
  esac
}

check_url "General internet" "https://www.google.com"
check_url "OpenAI API" "https://api.openai.com"
check_url "Mistral API" "https://api.mistral.ai"
check_url "GitHub" "https://github.com"

# ── 4. Environment / API keys ────────────────────────────────────────────────
section "4. SciNova .env (OpenAI + Mistral)"

ENV_FILE="$SCINOVA_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  pass ".env found at $ENV_FILE"
  if grep -qE '^OPENAI_API_KEY=sk-' "$ENV_FILE" 2>/dev/null; then
    pass "OPENAI_API_KEY set"
  else
    warn "OPENAI_API_KEY missing or placeholder — agents need OpenAI"
  fi
  if grep -qE '^MISTRAL_API_KEY=.+' "$ENV_FILE" 2>/dev/null \
    && ! grep -q 'your-mistral-api-key' "$ENV_FILE" 2>/dev/null; then
    pass "MISTRAL_API_KEY set"
  else
    warn "MISTRAL_API_KEY missing — SLM-routed tasks may fail"
  fi
  if grep -q "scinova-dev-secret-change-in-production" "$ENV_FILE" 2>/dev/null; then
    warn "SECRET_KEY still default — change before sharing access"
  else
    pass "SECRET_KEY customized"
  fi
  if grep -q '^CORS_ORIGINS=' "$ENV_FILE" 2>/dev/null; then
    info "CORS_ORIGINS: $(grep '^CORS_ORIGINS=' "$ENV_FILE" | cut -d= -f2-)"
  else
    warn "CORS_ORIGINS not in .env — add your http://PUBLIC_IP:5173"
  fi
else
  warn "No .env — run: cp .env.example .env && nano .env"
fi

# ── 5. Docker ────────────────────────────────────────────────────────────────
section "5. Docker"

if command -v docker >/dev/null 2>&1; then
  pass "Docker: $(docker --version 2>&1 | head -1)"
  if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose: $(docker compose version 2>&1 | head -1)"
  else
    fail "docker compose plugin not found"
  fi
  if docker info >/dev/null 2>&1; then
    pass "Docker daemon responding"
  elif sudo docker info >/dev/null 2>&1; then
    warn "Docker works with sudo only — re-login after: sudo usermod -aG docker \$USER"
  else
    fail "Docker daemon not running"
  fi
else
  fail "Docker not installed"
  info "Run: curl -fsSL https://get.docker.com | sudo sh"
fi

# ── 6. Running stack ─────────────────────────────────────────────────────────
section "6. SciNova stack"

if [ -d "$SCINOVA_DIR" ]; then
  pass "Repo: $SCINOVA_DIR"
else
  skip "Clone repo to $SCINOVA_DIR first"
fi

if [ -f "$SCINOVA_DIR/docker-compose.yml" ] && command -v docker >/dev/null 2>&1; then
  RUNNING=$(cd "$SCINOVA_DIR" && docker compose ps --status running -q 2>/dev/null | wc -l | tr -d ' ')
  if [ "${RUNNING:-0}" -gt 0 ]; then
    pass "Containers running: $RUNNING"
    BACKEND_CODE=$(http_code "http://127.0.0.1:8000/health")
    FRONTEND_CODE=$(http_code "http://127.0.0.1:5173/")
    if [ "$BACKEND_CODE" = "200" ]; then pass "Backend /health → 200"; else warn "Backend /health → $BACKEND_CODE"; fi
    if [ "$FRONTEND_CODE" = "200" ]; then pass "Frontend :5173 → 200"; else warn "Frontend :5173 → $FRONTEND_CODE"; fi
  else
    skip "Stack not running — ./scripts/deploy-azure.sh"
  fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────
section "Summary"
echo ""
echo "  PASS: $PASS   WARN: $WARN   FAIL: $FAIL   SKIP: $SKIP"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}Ready for Azure deploy${NC} (resolve WARN items for production)."
  exit 0
fi

echo -e "${RED}Fix FAIL items before deploy.${NC}"
exit 1
