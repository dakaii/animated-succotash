#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA="${ROOT}/infra"

cd "${INFRA}"

if ! command -v pulumi >/dev/null 2>&1; then
  echo "Install Pulumi first: https://www.pulumi.com/docs/install/"
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Install gcloud CLI first: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

echo "=== Hermes GCP setup ==="
echo

read -rp "GCP project ID: " PROJECT_ID
read -rp "GCP zone [us-central1-a]: " ZONE
ZONE="${ZONE:-us-central1-a}"

pulumi stack init dev 2>/dev/null || pulumi stack select dev

pulumi config set gcp:project "${PROJECT_ID}"
pulumi config set gcp:zone "${ZONE}"

echo
echo "=== API keys (stored as Pulumi secrets -> GCP Secret Manager) ==="
echo

read -rsp "OpenRouter API key: " OPENROUTER_KEY
echo
read -rsp "Telegram bot token (from @BotFather): " TELEGRAM_TOKEN
echo
read -rsp "Telegram user ID (from @userinfobot): " TELEGRAM_USER
echo
read -rsp "GitHub PAT (repo + PR scopes, optional — press Enter to skip): " GITHUB_PAT
echo

pulumi config set --secret openrouter_api_key "${OPENROUTER_KEY}"
pulumi config set --secret telegram_bot_token "${TELEGRAM_TOKEN}"
pulumi config set --secret telegram_allowed_users "${TELEGRAM_USER}"
if [[ -n "${GITHUB_PAT}" ]]; then
  pulumi config set --secret github_pat "${GITHUB_PAT}"
fi

echo
echo "=== Optional settings ==="
read -rp "VM size [e2-medium]: " INSTANCE_TYPE
INSTANCE_TYPE="${INSTANCE_TYPE:-e2-medium}"
pulumi config set hermes:instance_type "${INSTANCE_TYPE}"

read -rp "Model [deepseek/deepseek-chat]: " MODEL
MODEL="${MODEL:-deepseek/deepseek-chat}"
pulumi config set hermes:model "${MODEL}"

echo
echo "=== Ingress (how the internet reaches Hermes) ==="
echo "  cloudflare-named — stable URL via Cloudflare Tunnel (recommended, default)"
echo "  traefik          — static GCP IP + Traefik + Let's Encrypt"
echo "  cloudflare-quick — free random *.trycloudflare.com URL"
echo "  none             — no public URL (Telegram polling only)"
echo
read -rp "Ingress mode [cloudflare-named/traefik/cloudflare-quick/none] (default cloudflare-named): " INGRESS_MODE
INGRESS_MODE="${INGRESS_MODE:-cloudflare-named}"
pulumi config set hermes:ingress_mode "${INGRESS_MODE}"

case "${INGRESS_MODE}" in
  traefik)
    read -rp "Hostname (e.g. bot.yourdomain.com): " HOSTNAME
    read -rp "Let's Encrypt email: " ACME_EMAIL
    pulumi config set hermes:hostname "${HOSTNAME}"
    pulumi config set hermes:acme_email "${ACME_EMAIL}"
    read -rp "Use Telegram webhooks via https://${HOSTNAME}/telegram? [Y/n]: " USE_WEBHOOK
    if [[ "${USE_WEBHOOK}" =~ ^[Nn]$ ]]; then
      pulumi config set hermes:telegram_webhook false
    else
      pulumi config set hermes:telegram_webhook true
    fi
    echo
    echo "After pulumi up, create a DNS A record pointing ${HOSTNAME} to the static_ip output."
    ;;
  cloudflare-named)
    if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
      echo
      echo "Set CLOUDFLARE_API_TOKEN before pulumi up."
      echo "Permissions: Account Cloudflare Tunnel Edit, Zone DNS Edit"
      echo
    fi
    read -rp "Cloudflare account ID: " CF_ACCOUNT_ID
    read -rp "Cloudflare zone ID: " CF_ZONE_ID
    read -rp "Hostname (e.g. bot.yourdomain.com): " HOSTNAME
    pulumi config set cloudflare:account_id "${CF_ACCOUNT_ID}"
    pulumi config set cloudflare:zone_id "${CF_ZONE_ID}"
    pulumi config set cloudflare:hostname "${HOSTNAME}"
    pulumi config set hermes:hostname "${HOSTNAME}"
    read -rp "Use Telegram webhooks? [Y/n]: " USE_WEBHOOK
    if [[ "${USE_WEBHOOK}" =~ ^[Nn]$ ]]; then
      pulumi config set hermes:telegram_webhook false
    else
      pulumi config set hermes:telegram_webhook true
    fi
    ;;
  cloudflare-quick)
    read -rp "Use Telegram webhooks (needs quick tunnel URL)? [y/N]: " USE_WEBHOOK
    if [[ "${USE_WEBHOOK}" =~ ^[Yy]$ ]]; then
      pulumi config set hermes:telegram_webhook true
    else
      pulumi config set hermes:telegram_webhook false
    fi
    ;;
  none)
    pulumi config set hermes:telegram_webhook false
    ;;
esac

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

echo
echo "Enabling GCP APIs..."
gcloud services enable \
  compute.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iap.googleapis.com \
  --project="${PROJECT_ID}"

echo
echo "Ready. Deploy with:"
echo "  cd infra && pulumi up"
echo
echo "After deploy, message your Telegram bot. No SSH required for daily use."
