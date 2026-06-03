#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA="${ROOT}/infra"
STACK="${1:-dev}"

cd "${INFRA}"
pulumi stack select "${STACK}" >/dev/null 2>&1 || {
  echo "Stack '${STACK}' not found. Run ./scripts/setup.sh first."
  exit 1
}

URL="$(pulumi stack output public_url 2>/dev/null || true)"
if [[ -n "${URL}" && "${URL}" != "null" ]]; then
  echo "${URL}"
  exit 0
fi

CMD="$(pulumi stack output tunnel_url_command)"
eval "${CMD}"
