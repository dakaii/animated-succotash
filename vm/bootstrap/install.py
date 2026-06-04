from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from .settings import Settings

LOG = logging.getLogger("hermes.bootstrap")


def run(
    cmd: list[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    LOG.info("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, cwd=cwd)


def format_data_disk(settings: Settings) -> None:
    device = Path("/dev/disk/by-id/google-hermes-data")
    if not device.exists():
        LOG.info("Persistent data disk not found; using boot disk only")
        return

    if run(["blkid", str(device)], check=False).returncode != 0:
        LOG.info("Formatting persistent data disk")
        run(["mkfs.ext4", "-F", str(device)])

    fstab = Path("/etc/fstab")
    mount_entry = f"{device} {settings.hermes_home} ext4 defaults,nofail 0 2\n"
    if str(settings.hermes_home) not in fstab.read_text():
        fstab.write_text(fstab.read_text() + mount_entry)

    run(["mount", "-a"], check=False)


def install_packages() -> None:
    if shutil.which("python3") and shutil.which("curl"):
        return
    run(["apt-get", "update", "-qq"])
    run(["apt-get", "install", "-y", "-qq", "python3", "curl", "ca-certificates"])


def install_docker() -> None:
    if shutil.which("docker"):
        return
    LOG.info("Installing Docker")
    run(["bash", "-c", "curl -fsSL https://get.docker.com | sh"])
    run(["systemctl", "enable", "docker"])
    run(["systemctl", "start", "docker"])


def install_cloudflared(settings: Settings) -> None:
    if not settings.ingress_mode.startswith("cloudflare"):
        return
    if shutil.which("cloudflared"):
        return
    LOG.info("Installing cloudflared")
    target = Path("/usr/local/bin/cloudflared")
    run(["curl", "-fsSL", "-o", str(target), 
         "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"])
    target.chmod(0o755)


def install_compose_files(settings: Settings) -> None:
    source = settings.bundle_dir / "docker-compose.yml"
    target = settings.compose_dir / "docker-compose.yml"
    shutil.copy2(source, target)
    LOG.info("Installed %s", target)
