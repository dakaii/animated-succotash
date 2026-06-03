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

PROJECT="$(pulumi stack output project_id)"
ZONE="$(pulumi stack output zone)"
VM="$(pulumi stack output vm_name)"

echo "=== Hermes health check ==="
echo "Project: ${PROJECT}"
echo "VM:      ${VM} (${ZONE})"
echo

run_remote() {
  gcloud compute ssh "${VM}" \
    --zone="${ZONE}" \
    --project="${PROJECT}" \
    --tunnel-through-iap \
    --command="$1" 2>/dev/null
}

echo "--- Startup log (last 15 lines) ---"
run_remote "sudo tail -15 /var/log/hermes/startup.log 2>/dev/null || echo 'No startup log yet'" || true

echo
echo "--- Docker container ---"
run_remote "sudo docker ps --filter name=hermes --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" || {
  echo "Could not reach VM via IAP. Is it still booting?"
  exit 1
}

echo
echo "--- Hermes gateway ---"
run_remote "sudo docker exec hermes hermes gateway status 2>/dev/null || echo 'Gateway not ready'" || true

echo
echo "--- Cloudflare tunnel ---"
run_remote "sudo cat /var/log/hermes/tunnel-url.txt 2>/dev/null || echo 'No tunnel URL (disabled or still starting)'" || true

echo
echo "--- Recent Hermes logs ---"
run_remote "sudo docker logs hermes --tail 20 2>&1" || true
