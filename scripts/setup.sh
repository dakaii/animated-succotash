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
