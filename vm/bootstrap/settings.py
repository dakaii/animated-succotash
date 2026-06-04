from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_id: str
    model: str
    ingress_mode: str
    public_hostname: str
    telegram_webhook: bool
    bundle_dir: Path = Path("/opt/hermes-bundle")
    hermes_home: Path = Path("/opt/hermes-data")
    log_dir: Path = Path("/var/log/hermes")
    compose_dir: Path = Path("/opt/hermes")
    bootstrap_marker: Path = Path("/var/lib/hermes/bootstrapped")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            project_id=os.environ["PROJECT_ID"],
            model=os.environ["MODEL"],
            ingress_mode=os.environ["INGRESS_MODE"],
            public_hostname=os.environ.get("PUBLIC_HOSTNAME", ""),
            telegram_webhook=os.environ.get("TELEGRAM_WEBHOOK", "false").lower() == "true",
            bundle_dir=Path(os.environ.get("BUNDLE_DIR", "/opt/hermes-bundle")),
        )

    def ensure_layout(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.hermes_home.mkdir(parents=True, exist_ok=True)
        self.compose_dir.mkdir(parents=True, exist_ok=True)
        self.bootstrap_marker.parent.mkdir(parents=True, exist_ok=True)
        Path("/etc/hermes").mkdir(parents=True, exist_ok=True)
