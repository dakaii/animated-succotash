#!/bin/bash

install_packages() {
  if command -v jq >/dev/null 2>&1; then
    return
  fi
  log "Installing jq"
  apt-get update -qq
  apt-get install -y -qq jq curl
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    return
  fi
  log "Installing Docker"
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
}

install_cloudflared() {
  if [[ "${INGRESS_MODE}" != cloudflare-* ]]; then
    return
  fi
  if command -v cloudflared >/dev/null 2>&1; then
    return
  fi
  log "Installing cloudflared"
  curl -fsSL -o /usr/local/bin/cloudflared \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x /usr/local/bin/cloudflared
}

install_compose_files() {
  log "Installing docker-compose from bundle"
  cp "${BUNDLE_DIR}/docker-compose.yml" "${COMPOSE_DIR}/docker-compose.yml"
}
