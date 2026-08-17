#!/usr/bin/env bash
# SciNova OS — one-shot EC2 setup (Docker + git clone/pull + Bedrock .env + compose)
#
# Run ON the EC2 instance (ec2-user on Amazon Linux, or ubuntu), with sudo:
#
#   curl -fsSL https://raw.githubusercontent.com/saurabhdsh/scinova-os/main/scripts/setup_ec2.sh | bash
#   # or, after clone:
#   bash scripts/setup_ec2.sh
#
# Optional env vars before running:
#   REPO_URL=https://github.com/saurabhdsh/scinova-os.git
#   BRANCH=main
#   INSTALL_DIR=$HOME/SciNova-OS
#   GITHUB_TOKEN=...          # only if the repo is private
#   PUBLIC_HOST=52.0.130.62   # Elastic IP / DNS used in CORS
#   SKIP_BEDROCK_TEST=1
#   SKIP_COMPOSE=1

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/saurabhdsh/scinova-os.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/SciNova-OS}"
PUBLIC_HOST="${PUBLIC_HOST:-52.0.130.62}"
AWS_REGION="${AWS_REGION:-us-east-1}"
BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}WARN${NC} $*"; }
fail()  { echo -e "${RED}FAIL${NC} $*"; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || return 1
}

# ---------------------------------------------------------------------------
# 1) System packages + Docker
# ---------------------------------------------------------------------------
# Amazon Linux 2023 ships curl-minimal; installing "curl" conflicts. Never
# install curl if curl or curl-minimal is already present.
install_awscli() {
  need_cmd aws && return 0
  info "Installing AWS CLI v2…"
  tmp="$(mktemp -d)"
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "$tmp/awscliv2.zip"
  unzip -q "$tmp/awscliv2.zip" -d "$tmp"
  sudo "$tmp/aws/install" || sudo "$tmp/aws/install" --update
  rm -rf "$tmp"
}

ensure_compose_plugin() {
  if docker compose version >/dev/null 2>&1 || sudo docker compose version >/dev/null 2>&1; then
    return 0
  fi
  info "Installing Docker Compose plugin…"
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -fsSL \
    "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
}

info "Installing base packages (git, unzip, jq — skip curl on Amazon Linux)…"
if need_cmd apt-get; then
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates git unzip jq
  install_awscli
elif need_cmd dnf; then
  sudo dnf install -y git unzip jq
  install_awscli
elif need_cmd yum; then
  sudo yum install -y git unzip jq
  install_awscli
else
  warn "Unknown package manager — ensure git, docker, aws are installed."
fi

if ! need_cmd docker; then
  info "Installing Docker Engine…"
  if need_cmd dnf; then
    sudo dnf install -y docker
    sudo systemctl enable --now docker
  elif need_cmd yum; then
    sudo yum install -y docker
    sudo systemctl enable --now docker
  else
    curl -fsSL https://get.docker.com | sudo sh
  fi
fi

ensure_compose_plugin

if ! docker compose version >/dev/null 2>&1 && ! sudo docker compose version >/dev/null 2>&1; then
  fail "docker compose plugin missing after install."
fi

if ! groups | grep -q '\bdocker\b'; then
  info "Adding $USER to docker group…"
  sudo usermod -aG docker "$USER" || true
  warn "You may need to log out/in (or run: newgrp docker) if docker commands fail with permission denied."
fi

# Prefer sudo docker if socket not writable yet
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

info "Docker: $(${DOCKER[@]} --version)"
info "Compose: $(${DOCKER[@]} compose version)"

# ---------------------------------------------------------------------------
# 2) Clone or update repo
# ---------------------------------------------------------------------------
clone_url="$REPO_URL"
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  # https://github.com/org/repo.git → https://TOKEN@github.com/org/repo.git
  clone_url="$(echo "$REPO_URL" | sed -E "s#https://#https://${GITHUB_TOKEN}@#")"
fi

if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "Updating existing clone at $INSTALL_DIR…"
  git -C "$INSTALL_DIR" fetch origin
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH" || \
    git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
else
  info "Cloning $REPO_URL → $INSTALL_DIR (branch $BRANCH)…"
  rm -rf "$INSTALL_DIR"
  git clone --branch "$BRANCH" --single-branch "$clone_url" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
info "Commit: $(git log -1 --oneline)"

# ---------------------------------------------------------------------------
# 3) .env for Bedrock on EC2 (IAM role — no access keys)
# ---------------------------------------------------------------------------
ENV_FILE="$INSTALL_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  warn ".env already exists — leaving it in place (backup → .env.bak.$$)"
  cp -a "$ENV_FILE" "$ENV_FILE.bak.$$"
else
  info "Writing Bedrock-oriented .env…"
  SECRET_KEY="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)"
  PUBLIC_DNS="ec2-${PUBLIC_HOST//./-}.compute-1.amazonaws.com"
  cat > "$ENV_FILE" <<EOF
# Generated by scripts/setup_ec2.sh — do not commit
DEFAULT_LLM_PROVIDER=bedrock
ENABLED_LLM_PROVIDERS=openai,bedrock
BEDROCK_ENABLED=true
AWS_REGION=${AWS_REGION}
BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID}
BEDROCK_ONTOLOGY_MODEL_ID=${BEDROCK_MODEL_ID}
# Use IAM instance role on EC2 — do not set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY

SECRET_KEY=${SECRET_KEY}
DEBUG=false
LOG_LEVEL=INFO

CORS_ORIGINS=http://${PUBLIC_HOST}:5173,http://${PUBLIC_DNS}:5173,http://localhost:5173
VITE_ALLOW_ALL_HOSTS=true
EOF
fi

# Strip static keys so instance role is used
if grep -qE '^AWS_ACCESS_KEY_ID=|^AWS_SECRET_ACCESS_KEY=' "$ENV_FILE" 2>/dev/null; then
  warn "Commenting out AWS access keys in .env so WeaveEC2BedrockRole is used…"
  sed -i.bak -E 's/^(AWS_ACCESS_KEY_ID=)/# \1/; s/^(AWS_SECRET_ACCESS_KEY=)/# \1/' "$ENV_FILE"
fi

# ---------------------------------------------------------------------------
# 4) IAM / Bedrock smoke check
# ---------------------------------------------------------------------------
info "Checking instance identity (expect WeaveEC2BedrockRole)…"
if aws sts get-caller-identity --region "$AWS_REGION" >/tmp/scinova-sts.json 2>/tmp/scinova-sts.err; then
  cat /tmp/scinova-sts.json
else
  warn "STS failed — attach IAM instance profile WeaveEC2BedrockRole and retry."
  cat /tmp/scinova-sts.err || true
fi

if [[ "${SKIP_BEDROCK_TEST:-0}" != "1" && -x "$INSTALL_DIR/scripts/test-bedrock.sh" ]]; then
  info "Running Bedrock smoke test…"
  chmod +x "$INSTALL_DIR/scripts/test-bedrock.sh" || true
  if ! "$INSTALL_DIR/scripts/test-bedrock.sh"; then
    warn "Bedrock smoke test failed — fix model access / IAM, then re-run test."
    warn "Continuing with docker compose so the UI still comes up…"
  fi
fi

# ---------------------------------------------------------------------------
# 5) Docker Compose up
# ---------------------------------------------------------------------------
if [[ "${SKIP_COMPOSE:-0}" == "1" ]]; then
  warn "SKIP_COMPOSE=1 — not starting containers."
else
  info "Building and starting docker compose stack…"
  ${DOCKER[@]} compose -f "$INSTALL_DIR/docker-compose.yml" up -d --build
  ${DOCKER[@]} compose -f "$INSTALL_DIR/docker-compose.yml" ps
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
cat <<EOF

${GREEN}SciNova OS setup finished.${NC}

  Repo:      $INSTALL_DIR
  Frontend:  http://${PUBLIC_HOST}:5173
  Backend:   http://${PUBLIC_HOST}:8000
  API docs:  http://${PUBLIC_HOST}:8000/docs

Useful:
  cd $INSTALL_DIR
  docker compose logs -f backend
  docker compose ps
  ./scripts/test-bedrock.sh

If docker permission denied:
  newgrp docker
  # or re-SSH, then: cd $INSTALL_DIR && docker compose up -d

EOF
