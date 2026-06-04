from __future__ import annotations

import logging
import time

from .install import run
from .settings import Settings

LOG = logging.getLogger("hermes.bootstrap")


def start_hermes(settings: Settings) -> None:
    LOG.info("Starting Hermes Agent")
    cwd = settings.compose_dir
    run(["docker", "compose", "pull"], check=False, cwd=cwd)
    run(["docker", "compose", "up", "-d"], cwd=cwd)

    for _ in range(30):
        result = run(["docker", "exec", "hermes", "hermes", "doctor"], check=False)
        if result.returncode == 0:
            _ensure_node()
            LOG.info("Hermes is healthy")
            return
        time.sleep(5)

    LOG.warning("Hermes doctor did not pass within timeout")


def ensure_services(settings: Settings) -> None:
    run(["docker", "compose", "up", "-d"], check=False, cwd=settings.compose_dir)
    if settings.ingress_mode.startswith("cloudflare"):
        run(["systemctl", "restart", "cloudflared-hermes"], check=False)


def _ensure_node() -> None:
    result = run(["docker", "exec", "hermes", "command", "-v", "npx"], check=False)
    if result.returncode == 0:
        return
    LOG.info("Installing Node.js in Hermes container for GitHub MCP")
    run(
        [
            "docker",
            "exec",
            "hermes",
            "bash",
            "-c",
            "apt-get update -qq && apt-get install -y -qq nodejs npm",
        ],
        check=False,
    )
