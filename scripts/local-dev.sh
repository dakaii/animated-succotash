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

if [[ ! -f config.yaml ]]; then
  cp config.yaml.example config.yaml
  echo "Created hermes/config.yaml from example."
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
