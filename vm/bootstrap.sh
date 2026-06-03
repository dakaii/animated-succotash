#!/bin/bash
set -euo pipefail

for lib in "${BUNDLE_DIR}/lib/"*.sh; do
  # shellcheck source=/dev/null
  source "${lib}"
done

run_bootstrap() {
  ensure_layout
  format_data_disk
  install_packages
  install_docker
  install_cloudflared
  install_compose_files

  if [[ "${INGRESS_MODE}" == cloudflare-* && "${TELEGRAM_WEBHOOK}" == "true" ]]; then
    start_cloudflared
  fi

  write_config
  start_hermes

  if [[ "${INGRESS_MODE}" == cloudflare-* && "${TELEGRAM_WEBHOOK}" != "true" ]]; then
    start_cloudflared
  fi

  date -Iseconds > "${BOOTSTRAP_MARKER}"
  log "Setup complete (ingress: ${INGRESS_MODE})"
  if [[ "${TELEGRAM_WEBHOOK}" == "true" ]]; then
    log "Telegram webhook mode enabled"
  else
    log "Telegram polling mode — VM connects outbound to Telegram"
  fi
  if [[ -f "${LOG_DIR}/tunnel-url.txt" ]]; then
    log "Public URL: $(cat "${LOG_DIR}/tunnel-url.txt")"
  fi
}

if [[ -f "${BOOTSTRAP_MARKER}" ]]; then
  ensure_layout
  install_packages
  install_docker
  ensure_services
  exit 0
fi

run_bootstrap
