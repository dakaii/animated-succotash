#!/bin/bash

write_config() {
  local openrouter_key telegram_token telegram_users github_pat webhook_url webhook_secret

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

  if [[ "${TELEGRAM_WEBHOOK}" == "true" ]]; then
    if [[ -n "${PUBLIC_HOSTNAME}" && "${INGRESS_MODE}" != "cloudflare-quick" ]]; then
      webhook_url="https://${PUBLIC_HOSTNAME}/telegram"
    elif [[ -f "${LOG_DIR}/tunnel-url.txt" ]]; then
      webhook_url="$(cat "${LOG_DIR}/tunnel-url.txt")/telegram"
    fi
    if [[ -n "${webhook_url:-}" ]]; then
      webhook_secret="$(openssl rand -hex 32)"
      cat >> "${HERMES_HOME}/.env" <<EOF
TELEGRAM_WEBHOOK_URL=${webhook_url}
TELEGRAM_WEBHOOK_SECRET=${webhook_secret}
EOF
    fi
  fi

  sed "s/\${MODEL}/${MODEL}/" "${BUNDLE_DIR}/hermes.config.yaml.tpl" > "${HERMES_HOME}/config.yaml"
  if [[ -n "${github_pat}" ]]; then
    sed "s/\${GITHUB_PAT}/${github_pat}/" \
      "${BUNDLE_DIR}/hermes.github-mcp.yaml.tpl" >> "${HERMES_HOME}/config.yaml"
  fi

  chmod 600 "${HERMES_HOME}/.env" "${HERMES_HOME}/config.yaml"
  chown -R root:root "${HERMES_HOME}"
}
