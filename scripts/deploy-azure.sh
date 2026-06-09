#!/usr/bin/env bash
# SciNova OS — deploy on Azure Ubuntu VM (Docker Compose)
#
# Prereqs: Ubuntu 22.04/24.04 VM, ports 22 + 5173 open in NSG
#
# Usage (on the VM):
#   export SCINOVA_REPO_URL=https://github.com/saurabhdsh/scinova-os.git
#   curl -fsSL <raw-url>/scripts/deploy-azure.sh | bash
#   # or after git clone:
#   cd ~/scinova-os && chmod +x scripts/deploy-azure.sh && ./scripts/deploy-azure.sh

set -euo pipefail

SCINOVA_DIR="${SCINOVA_DIR:-$HOME/scinova-os}"
SCINOVA_REPO_URL="${SCINOVA_REPO_URL:-https://github.com/saurabhdsh/scinova-os.git}"
SCINOVA_BRANCH="${SCINOVA_BRANCH:-main}"

log() { echo "[deploy-azure] $*"; }
die() { echo "[deploy-azure] ERROR: $*" >&2; exit 1; }

azure_public_ip() {
  local ip
  ip=$(curl -sf -H "Metadata:true" --connect-timeout 2 \
    "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" \
    2>/dev/null | tr -d '[:space:]' || true)
  if [ -n "$ip" ] && [ "$ip" != "null" ]; then
    echo "$ip"
    return
  fi
  curl -sf --connect-timeout 3 https://ifconfig.me 2>/dev/null || echo ""
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker already installed"
    return
  fi
  log "Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
  log "Docker installed — if 'permission denied', log out and SSH back in, then re-run this script"
}

clone_or_update() {
  if [ -d "$SCINOVA_DIR/.git" ]; then
    log "Updating repo at $SCINOVA_DIR"
    git -C "$SCINOVA_DIR" fetch origin
    git -C "$SCINOVA_DIR" checkout "$SCINOVA_BRANCH"
    git -C "$SCINOVA_DIR" pull --ff-only origin "$SCINOVA_BRANCH" || true
  else
    log "Cloning $SCINOVA_REPO_URL → $SCINOVA_DIR"
    git clone --branch "$SCINOVA_BRANCH" --depth 1 "$SCINOVA_REPO_URL" "$SCINOVA_DIR"
  fi
}

setup_env() {
  local ip="$1"
  local env_file="$SCINOVA_DIR/.env"
  if [ ! -f "$env_file" ]; then
    log "Creating .env from .env.example"
    cp "$SCINOVA_DIR/.env.example" "$env_file"
  fi

  if [ -n "$ip" ]; then
    local cors="http://${ip}:5173"
    if grep -q '^CORS_ORIGINS=' "$env_file"; then
      if ! grep -q "$ip" "$env_file"; then
        log "Set CORS_ORIGINS=$cors in .env (edit manually if you use a domain)"
        sed -i.bak "s|^CORS_ORIGINS=.*|CORS_ORIGINS=$cors|" "$env_file"
      fi
    else
      echo "CORS_ORIGINS=$cors" >> "$env_file"
    fi
  fi

  if grep -q "scinova-dev-secret-change-in-production" "$env_file" 2>/dev/null; then
    if command -v openssl >/dev/null 2>&1; then
      local secret
      secret=$(openssl rand -hex 32)
      sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$secret|" "$env_file"
      log "Generated random SECRET_KEY"
    fi
  fi

  chmod 600 "$env_file" 2>/dev/null || true

  if ! grep -qE '^OPENAI_API_KEY=sk-' "$env_file" 2>/dev/null; then
    log "IMPORTANT: Edit $env_file and set OPENAI_API_KEY and MISTRAL_API_KEY"
    log "  nano $env_file"
  fi
}

compose_up() {
  cd "$SCINOVA_DIR"
  export VITE_ALLOW_ALL_HOSTS=true
  log "Building images (first run may take 10–15 min)..."
  docker compose build
  log "Starting stack..."
  docker compose up -d
  log "Waiting for backend health..."
  for _ in $(seq 1 40); do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
      break
    fi
    sleep 3
  done
}

main() {
  PUBLIC_IP=$(azure_public_ip)
  install_docker
  clone_or_update
  setup_env "$PUBLIC_IP"
  compose_up

  echo ""
  echo "════════════════════════════════════════════════════════════"
  echo "  SciNova OS deploy finished"
  echo "════════════════════════════════════════════════════════════"
  if [ -n "$PUBLIC_IP" ]; then
    echo "  UI:      http://${PUBLIC_IP}:5173"
    echo "  API:     http://${PUBLIC_IP}:8000/docs"
  else
    echo "  UI:      http://<vm-public-ip>:5173"
  fi
  echo "  Login:   admin / admin123  (change in production)"
  echo ""
  echo "  Next:"
  echo "    nano $SCINOVA_DIR/.env     # OPENAI_API_KEY, MISTRAL_API_KEY"
  echo "    docker compose restart backend celery-worker frontend"
  echo "    ./scripts/preflight-azure.sh"
  echo ""
  echo "  Azure NSG: allow inbound TCP 5173 (and 22 for SSH)"
  echo "════════════════════════════════════════════════════════════"
}

main "$@"
