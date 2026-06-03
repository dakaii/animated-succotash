#!/bin/bash

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
