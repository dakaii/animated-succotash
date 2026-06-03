#!/bin/bash

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
