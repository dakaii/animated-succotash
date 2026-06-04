from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from .settings import Settings

LOG = logging.getLogger("hermes.bootstrap")


def metadata_token() -> str:
    request = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode())
    return payload["access_token"]


def fetch_secret(settings: Settings, secret_id: str) -> str | None:
    url = (
        f"https://secretmanager.googleapis.com/v1/projects/{settings.project_id}"
        f"/secrets/{secret_id}/versions/latest:access"
    )
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {metadata_token()}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        LOG.warning("Secret %s unavailable: %s", secret_id, exc)
        return None

    import base64

    data = payload.get("payload", {}).get("data")
    if not data:
        return None
    return base64.b64decode(data).decode()
