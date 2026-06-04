from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from . import cloudflared, config, hermes, install
from .settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="[hermes-setup] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)


def _log_file_handler(settings: Settings) -> None:
    settings.ensure_layout()
    file_handler = logging.FileHandler(settings.log_dir / "startup.log")
    file_handler.setFormatter(logging.Formatter("[hermes-setup] %(message)s"))
    logging.getLogger().addHandler(file_handler)


def run_bootstrap(settings: Settings) -> None:
    _log_file_handler(settings)
    settings.ensure_layout()

    install.format_data_disk(settings)
    install.install_packages()
    install.install_docker()
    install.install_cloudflared(settings)
    install.install_compose_files(settings)

    if settings.ingress_mode.startswith("cloudflare") and settings.telegram_webhook:
        cloudflared.start_cloudflared(settings)

    config.write_config(settings)
    hermes.start_hermes(settings)

    if settings.ingress_mode.startswith("cloudflare") and not settings.telegram_webhook:
        cloudflared.start_cloudflared(settings)

    settings.bootstrap_marker.write_text(datetime.now(timezone.utc).isoformat())
    logging.info("Setup complete (ingress: %s)", settings.ingress_mode)
    if settings.telegram_webhook:
        logging.info("Telegram webhook mode enabled")
    else:
        logging.info("Telegram polling mode — VM connects outbound to Telegram")

    tunnel_file = settings.log_dir / "tunnel-url.txt"
    if tunnel_file.exists():
        logging.info("Public URL: %s", tunnel_file.read_text().strip())


def main() -> None:
    settings = Settings.from_env()
    if settings.bootstrap_marker.exists():
        _log_file_handler(settings)
        settings.ensure_layout()
        install.install_packages()
        install.install_docker()
        hermes.ensure_services(settings)
        logging.info(
            "Already bootstrapped at %s; ensuring services are running",
            settings.bootstrap_marker.read_text().strip(),
        )
        return

    run_bootstrap(settings)


if __name__ == "__main__":
    main()
