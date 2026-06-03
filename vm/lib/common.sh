#!/bin/bash
# Shared paths and logging.

HERMES_HOME="${HERMES_HOME:-/opt/hermes-data}"
LOG_DIR="${LOG_DIR:-/var/log/hermes}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/hermes}"
BOOTSTRAP_MARKER="${BOOTSTRAP_MARKER:-/var/lib/hermes/bootstrapped}"
BUNDLE_DIR="${BUNDLE_DIR:-/opt/hermes-bundle}"

log() {
  echo "[hermes-setup] $*" | tee -a "${LOG_DIR}/startup.log"
}

ensure_layout() {
  mkdir -p "${LOG_DIR}" "${HERMES_HOME}" "${COMPOSE_DIR}" /var/lib/hermes /etc/hermes
}
