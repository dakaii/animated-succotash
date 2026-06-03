#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES="${ROOT}/hermes"

cd "${HERMES}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created hermes/.env — edit it with your keys, then re-run this script."
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

if [[ ! -f config.yaml ]]; then
  cp config.yaml.example config.yaml
fi

if [[ -n "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  python3 - <<'PY'
import os
import re
from pathlib import Path

config_path = Path("config.yaml")
text = config_path.read_text()
token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
if token:
    text = text.replace("${GITHUB_PERSONAL_ACCESS_TOKEN}", token)
    text = text.replace("github_pat_your_token", token)
    config_path.write_text(text)
PY
fi

mkdir -p data

docker compose pull
docker compose up -d

echo
echo "Hermes is starting locally."
echo "  Logs:    docker compose -f ${HERMES}/docker-compose.yml logs -f"
echo "  Doctor:  docker exec hermes hermes doctor"
echo "  Status:  docker exec hermes hermes gateway status"
echo
echo "Message your Telegram bot once the gateway is running."

if ! docker exec hermes command -v npx >/dev/null 2>&1; then
  echo
  echo "Installing Node.js for GitHub MCP..."
  docker exec hermes bash -c 'apt-get update -qq && apt-get install -y -qq nodejs npm' || true
fi
