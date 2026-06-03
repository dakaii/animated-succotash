#!/bin/bash
set -euo pipefail

PROJECT_ID="__PROJECT_ID__"
MODEL="__MODEL__"
ENABLE_CLOUDFLARE_TUNNEL="__ENABLE_CLOUDFLARE_TUNNEL__"
TELEGRAM_WEBHOOK="__TELEGRAM_WEBHOOK__"

HERMES_HOME="/opt/hermes-data"
LOG_DIR="/var/log/hermes"
COMPOSE_DIR="/opt/hermes"
BOOTSTRAP_MARKER="/var/lib/hermes/bootstrapped"

log() {
  echo "[hermes-setup] $*" | tee -a "${LOG_DIR}/startup.log"
}

mkdir -p "${LOG_DIR}" "${HERMES_HOME}" "${COMPOSE_DIR}" /var/lib/hermes

install_packages() {
  if command -v jq >/dev/null 2>&1; then
    return
  fi
  log "Installing jq"
  apt-get update -qq
  apt-get install -y -qq jq curl
}

metadata_token() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
    | jq -r .access_token
}

fetch_secret() {
  local secret_id="$1"
  local token payload

  token="$(metadata_token)"
  payload="$(curl -sf \
    -H "Authorization: Bearer ${token}" \
    "https://secretmanager.googleapis.com/v1/projects/${PROJECT_ID}/secrets/${secret_id}/versions/latest:access" \
    | jq -r .payload.data)" || return 1

  if [[ -z "${payload}" || "${payload}" == "null" ]]; then
    return 1
  fi

  echo "${payload}" | base64 -d
}

format_data_disk() {
  local device="/dev/disk/by-id/google-hermes-data"
  if [[ ! -b "${device}" ]]; then
    log "Persistent data disk not found; using boot disk only"
    return
  fi

  if ! blkid "${device}" >/dev/null 2>&1; then
    log "Formatting persistent data disk"
    mkfs.ext4 -F "${device}"
  fi

  if ! grep -q "${HERMES_HOME}" /etc/fstab; then
    echo "${device} ${HERMES_HOME} ext4 defaults,nofail 0 2" >> /etc/fstab
  fi

  mount -a
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
  if [[ "${ENABLE_CLOUDFLARE_TUNNEL}" != "true" ]]; then
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

write_compose() {
  local extra_ports=""
  if [[ "${TELEGRAM_WEBHOOK}" == "true" ]]; then
    extra_ports=$'      - "8443:8443"\n'
  fi

  cat > "${COMPOSE_DIR}/docker-compose.yml" <<EOF
services:
  hermes:
    image: nousresearch/hermes-agent:latest
    container_name: hermes
    restart: unless-stopped
    command: gateway run
    ports:
      - "8642:8642"
      - "9119:9119"
${extra_ports}    volumes:
      - /opt/hermes-data:/root/.hermes
    environment:
      HERMES_DASHBOARD: "1"
      API_SERVER_ENABLED: "true"
      API_SERVER_HOST: "0.0.0.0"
      HERMES_ALLOW_ROOT_GATEWAY: "1"
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: "2.0"
EOF
}

write_config() {
  local openrouter_key telegram_token telegram_users github_pat webhook_url webhook_secret
  local mcp_block=""

  openrouter_key="$(fetch_secret openrouter-api-key || true)"
  telegram_token="$(fetch_secret telegram-bot-token || true)"
  telegram_users="$(fetch_secret telegram-allowed-users || true)"
  github_pat="$(fetch_secret github-pat || true)"

  if [[ -z "${openrouter_key}" || -z "${telegram_token}" || -z "${telegram_users}" ]]; then
    log "ERROR: Required secrets missing in Secret Manager"
    exit 1
  fi

  cat > "${HERMES_HOME}/.env" <<EOF
OPENROUTER_API_KEY=${openrouter_key}
TELEGRAM_BOT_TOKEN=${telegram_token}
TELEGRAM_ALLOWED_USERS=${telegram_users}
EOF

  if [[ "${TELEGRAM_WEBHOOK}" == "true" && -f "${LOG_DIR}/tunnel-url.txt" ]]; then
    webhook_url="$(cat "${LOG_DIR}/tunnel-url.txt")/telegram"
    webhook_secret="$(openssl rand -hex 32)"
    cat >> "${HERMES_HOME}/.env" <<EOF
TELEGRAM_WEBHOOK_URL=${webhook_url}
TELEGRAM_WEBHOOK_SECRET=${webhook_secret}
EOF
  fi

  if [[ -n "${github_pat}" ]]; then
    mcp_block=$(cat <<EOF

mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${github_pat}"
    tools:
      include:
        - list_issues
        - create_issue
        - update_issue
        - search_code
        - get_file_contents
        - create_or_update_file
        - create_pull_request
        - list_pull_requests
        - get_pull_request
        - create_pull_request_review
      prompts: false
      resources: false
EOF
)
  fi

  cat > "${HERMES_HOME}/config.yaml" <<EOF
model:
  default: "${MODEL}"
  provider: openrouter
  base_url: https://openrouter.ai/api/v1

platform_toolsets:
  telegram: [hermes-telegram]
${mcp_block}
EOF

  chmod 600 "${HERMES_HOME}/.env" "${HERMES_HOME}/config.yaml"
  chown -R root:root "${HERMES_HOME}"
}

start_cloudflared() {
  if [[ "${ENABLE_CLOUDFLARE_TUNNEL}" != "true" ]]; then
    return
  fi

  local tunnel_port="9119"
  if [[ "${TELEGRAM_WEBHOOK}" == "true" ]]; then
    tunnel_port="8443"
  fi

  log "Starting Cloudflare quick tunnel (port ${tunnel_port})"

  cat > /etc/systemd/system/cloudflared-hermes.service <<UNIT
[Unit]
Description=Cloudflare quick tunnel for Hermes
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:${tunnel_port} --protocol http2 --loglevel info
Restart=always
RestartSec=10
StandardOutput=append:/var/log/hermes/cloudflared.log
StandardError=append:/var/log/hermes/cloudflared.log

[Install]
WantedBy=multi-user.target
UNIT

  systemctl daemon-reload
  systemctl enable cloudflared-hermes
  systemctl restart cloudflared-hermes

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
  if [[ "${ENABLE_CLOUDFLARE_TUNNEL}" == "true" ]]; then
    systemctl restart cloudflared-hermes 2>/dev/null || true
  fi
}

run_bootstrap() {
  format_data_disk
  install_packages
  install_docker
  install_cloudflared
  write_compose

  if [[ "${ENABLE_CLOUDFLARE_TUNNEL}" == "true" && "${TELEGRAM_WEBHOOK}" == "true" ]]; then
    start_cloudflared
  fi

  write_config
  start_hermes

  if [[ "${ENABLE_CLOUDFLARE_TUNNEL}" == "true" && "${TELEGRAM_WEBHOOK}" != "true" ]]; then
    start_cloudflared
  fi

  date -Iseconds > "${BOOTSTRAP_MARKER}"
  log "Setup complete"
  log "Telegram uses outbound polling by default — no public URL required for messaging"
  if [[ -f "${LOG_DIR}/tunnel-url.txt" ]]; then
    log "Dashboard URL: $(cat "${LOG_DIR}/tunnel-url.txt")"
  fi
}

if [[ -f "${BOOTSTRAP_MARKER}" ]]; then
  log "Already bootstrapped at $(cat "${BOOTSTRAP_MARKER}"); ensuring services are running"
  install_packages
  install_docker
  ensure_services
  exit 0
fi

run_bootstrap
