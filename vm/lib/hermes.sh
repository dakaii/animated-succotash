#!/bin/bash

ensure_hermes_node() {
  if docker exec hermes command -v npx >/dev/null 2>&1; then
    return
  fi
  log "Installing Node.js in Hermes container for GitHub MCP"
  docker exec hermes bash -c \
    'apt-get update -qq && apt-get install -y -qq nodejs npm' \
    || log "WARNING: Could not install Node.js in container; GitHub MCP may not work"
}

start_hermes() {
  log "Starting Hermes Agent"
  cd "${COMPOSE_DIR}"
  docker compose pull
  docker compose up -d

  for _ in $(seq 1 30); do
    if docker exec hermes hermes doctor >/dev/null 2>&1; then
      ensure_hermes_node
      log "Hermes is healthy"
      return
    fi
    sleep 5
  done

  log "WARNING: Hermes doctor did not pass within timeout"
}

ensure_services() {
  cd "${COMPOSE_DIR}"
  docker compose up -d
  if [[ "${INGRESS_MODE}" == cloudflare-* ]]; then
    systemctl restart cloudflared-hermes 2>/dev/null || true
  fi
}
