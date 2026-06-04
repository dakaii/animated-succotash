from __future__ import annotations

import logging
import re
import shutil
import time
from pathlib import Path

from .install import run
from .secrets import fetch_secret
from .settings import Settings

LOG = logging.getLogger("hermes.bootstrap")


def _install_systemd_unit(unit_source: Path) -> None:
    target = Path("/etc/systemd/system/cloudflared-hermes.service")
    shutil.copy2(unit_source, target)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "cloudflared-hermes"])
    run(["systemctl", "restart", "cloudflared-hermes"])


def start_cloudflared(settings: Settings) -> None:
    if settings.ingress_mode == "cloudflare-named":
        _start_named(settings)
    elif settings.ingress_mode == "cloudflare-quick":
        _start_quick(settings)


def _start_named(settings: Settings) -> None:
    token = fetch_secret(settings, "cloudflare-tunnel-token")
    if not token:
        raise RuntimeError("cloudflare-tunnel-token missing from Secret Manager")

    LOG.info("Starting named Cloudflare tunnel for %s", settings.public_hostname)
    (settings.log_dir / "tunnel-url.txt").write_text(f"https://{settings.public_hostname}\n")
    token_path = Path("/etc/hermes/cloudflared-token")
    token_path.write_text(token)
    token_path.chmod(0o600)

    unit = settings.bundle_dir / "systemd" / "cloudflared-named.service"
    _install_systemd_unit(unit)


def _start_quick(settings: Settings) -> None:
    port = "8443" if settings.telegram_webhook else "9119"
    LOG.info("Starting Cloudflare quick tunnel on port %s", port)

    template = (settings.bundle_dir / "systemd" / "cloudflared-quick.service.tpl").read_text()
    rendered = template.replace("__TUNNEL_PORT__", port)
    temp_unit = Path("/tmp/cloudflared-quick.service")
    temp_unit.write_text(rendered)
    _install_systemd_unit(temp_unit)

    log_file = settings.log_dir / "cloudflared.log"
    pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    for _ in range(30):
        if log_file.exists() and "trycloudflare.com" in log_file.read_text():
            match = pattern.search(log_file.read_text())
            if match:
                (settings.log_dir / "tunnel-url.txt").write_text(match.group(0) + "\n")
                LOG.info("Tunnel URL: %s", match.group(0))
                return
        time.sleep(2)

    LOG.warning("Could not capture Cloudflare quick tunnel URL yet")
