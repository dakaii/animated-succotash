#!/bin/bash
set -euo pipefail

export PROJECT_ID="__PROJECT_ID__"
export MODEL="__MODEL__"
export INGRESS_MODE="__INGRESS_MODE__"
export PUBLIC_HOSTNAME="__PUBLIC_HOSTNAME__"
export TELEGRAM_WEBHOOK="__TELEGRAM_WEBHOOK__"
export BUNDLE_DIR="/opt/hermes-bundle"
export PYTHONPATH="${BUNDLE_DIR}"

exec python3 -B -m bootstrap
