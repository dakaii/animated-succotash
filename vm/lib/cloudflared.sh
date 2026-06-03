#!/bin/bash

install_systemd_unit() {
  local source="$1"
  cp "${source}" /etc/systemd/system/cloudflared-hermes.service
  systemctl daemon-reload
  systemctl enable cloudflared-hermes
  systemctl restart cloudflared-hermes
}

start_named_cloudflared() {
  local token
  token="$(fetch_secret cloudflare-tunnel-token || true)"
  if [[ -z "${token}" ]]; then
    log "ERROR: cloudflare-tunnel-token missing from Secret Manager"
    exit 1
  fi

  log "Starting named Cloudflare tunnel for ${PUBLIC_HOSTNAME}"
  echo "https://${PUBLIC_HOSTNAME}" > "${LOG_DIR}/tunnel-url.txt"
  echo "${token}" > /etc/hermes/cloudflared-token
  chmod 600 /etc/hermes/cloudflared-token

  install_systemd_unit "${BUNDLE_DIR}/systemd/cloudflared-named.service"
  log "Named tunnel URL: https://${PUBLIC_HOSTNAME}"
}

start_quick_cloudflared() {
  local tunnel_port="9119"
  local unit_file="/tmp/cloudflared-quick.service"

  if [[ "${TELEGRAM_WEBHOOK}" == "true" ]]; then
    tunnel_port="8443"
  fi

  log "Starting Cloudflare quick tunnel (port ${tunnel_port})"
  sed "s/__TUNNEL_PORT__/${tunnel_port}/" \
    "${BUNDLE_DIR}/systemd/cloudflared-quick.service.tpl" > "${unit_file}"
  install_systemd_unit "${unit_file}"

  for _ in $(seq 1 30); do
    if grep -q "trycloudflare.com" "${LOG_DIR}/cloudflared.log" 2>/dev/null; then
      grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "${LOG_DIR}/cloudflared.log" | head -1 \
        > "${LOG_DIR}/tunnel-url.txt"
      log "Tunnel URL: $(cat "${LOG_DIR}/tunnel-url.txt")"
      return
    fi
    sleep 2
  done

  log "WARNING: Could not capture Cloudflare tunnel URL yet"
}

start_cloudflared() {
  case "${INGRESS_MODE}" in
    cloudflare-named) start_named_cloudflared ;;
    cloudflare-quick) start_quick_cloudflared ;;
  esac
}
