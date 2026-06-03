#!/usr/bin/env bash
set -euo pipefail

# Re-run VM bootstrap after secret rotation or config changes.
# Removes the bootstrap marker and resets the instance.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA="${ROOT}/infra"
STACK="${1:-dev}"

cd "${INFRA}"
pulumi stack select "${STACK}" >/dev/null

PROJECT="$(pulumi stack output project_id)"
ZONE="$(pulumi stack output zone)"
VM="$(pulumi stack output vm_name)"

echo "This will reset ${VM} and re-run bootstrap on next boot."
read -rp "Continue? [y/N] " CONFIRM
[[ "${CONFIRM}" =~ ^[Yy]$ ]] || exit 0

gcloud compute ssh "${VM}" \
  --zone="${ZONE}" \
  --project="${PROJECT}" \
  --tunnel-through-iap \
  --command="sudo rm -f /var/lib/hermes/bootstrapped" 2>/dev/null || true

gcloud compute instances reset "${VM}" \
  --zone="${ZONE}" \
  --project="${PROJECT}"

echo "VM reset. Bootstrap will run in ~3-5 minutes."
echo "Check progress: ${ROOT}/scripts/health.sh"
