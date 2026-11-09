#!/usr/bin/env bash
# Compatibility entry point. The one-shot setup lives in scripts/setup_azure.sh.
# When this file is piped from curl, the sibling script is fetched from GitHub.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/setup_azure.sh" ]]; then
  exec "$SCRIPT_DIR/setup_azure.sh" "$@"
fi
curl -fsSL https://raw.githubusercontent.com/saurabhdsh/scinova-os/main/scripts/setup_azure.sh | bash
