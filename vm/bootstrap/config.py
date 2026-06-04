from __future__ import annotations

import logging
import secrets as pysecrets
from pathlib import Path

from .secrets import fetch_secret
from .settings import Settings

LOG = logging.getLogger("hermes.bootstrap")


def write_config(settings: Settings) -> None:
    openrouter = fetch_secret(settings, "openrouter-api-key")
    telegram_token = fetch_secret(settings, "telegram-bot-token")
    telegram_users = fetch_secret(settings, "telegram-allowed-users")
    github_pat = fetch_secret(settings, "github-pat")

    if not all([openrouter, telegram_token, telegram_users]):
        raise RuntimeError("Required secrets missing in Secret Manager")

    env_path = settings.hermes_home / ".env"
    env_lines = [
        f"OPENROUTER_API_KEY={openrouter}",
        f"TELEGRAM_BOT_TOKEN={telegram_token}",
        f"TELEGRAM_ALLOWED_USERS={telegram_users}",
    ]

    if settings.telegram_webhook:
        webhook_url = _webhook_url(settings)
        if webhook_url:
            env_lines.extend(
                [
                    f"TELEGRAM_WEBHOOK_URL={webhook_url}",
                    f"TELEGRAM_WEBHOOK_SECRET={pysecrets.token_hex(32)}",
                ]
            )

    env_path.write_text("\n".join(env_lines) + "\n")

    config_template = (settings.bundle_dir / "hermes.config.yaml.tpl").read_text()
    config_path = settings.hermes_home / "config.yaml"
    config_path.write_text(config_template.replace("${MODEL}", settings.model))

    if github_pat:
        mcp_template = (settings.bundle_dir / "hermes.github-mcp.yaml.tpl").read_text()
        with config_path.open("a") as handle:
            handle.write(mcp_template.replace("${GITHUB_PAT}", github_pat))

    env_path.chmod(0o600)
    config_path.chmod(0o600)


def _webhook_url(settings: Settings) -> str | None:
    if settings.public_hostname and settings.ingress_mode != "cloudflare-quick":
        return f"https://{settings.public_hostname}/telegram"
    tunnel_file = settings.log_dir / "tunnel-url.txt"
    if tunnel_file.exists():
        return f"{tunnel_file.read_text().strip()}/telegram"
    return None
