#!/usr/bin/env bash
set -euo pipefail

# Fetch the Cloudflare quick tunnel URL from a deployed VM.
# Usage: ./scripts/get-tunnel-url.sh [stack]

STACK="${1:-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT}/infra"
pulumi stack select "${STACK}" >/dev/null

CMD="$(pulumi stack output tunnel_url_command --show-secrets 2>/dev/null || pulumi stack output tunnel_url_command)"
eval "${CMD}"
