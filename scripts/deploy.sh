#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA="${ROOT}/infra"

cd "${INFRA}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

pulumi up "$@"

echo
echo "Deployment finished."
echo "  Health check:  ${ROOT}/scripts/health.sh"
echo "  Tunnel URL:    ${ROOT}/scripts/get-tunnel-url.sh"
