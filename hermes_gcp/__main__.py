from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .commands.deploy import cmd_deploy
from .commands.health import cmd_health
from .commands.ops import cmd_rebootstrap, cmd_tunnel_url
from .commands.setup import cmd_setup


def _local_dev(_: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    compose = root / "hermes" / "docker-compose.yml"
    if not compose.exists():
        print("Missing hermes/docker-compose.yml", file=sys.stderr)
        return 1
    return subprocess.call(["docker", "compose", "-f", str(compose), "up", "-d"], cwd=root / "hermes")


COMMANDS = {
    "setup": cmd_setup,
    "deploy": cmd_deploy,
    "health": cmd_health,
    "rebootstrap": cmd_rebootstrap,
    "tunnel-url": cmd_tunnel_url,
    "local-dev": _local_dev,
}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("Usage: python -m hermes_gcp <command> [args]\n")
        print("Commands:")
        for name in COMMANDS:
            print(f"  {name}")
        return 0 if argv and argv[0] in ("-h", "--help", "help") else 1

    cmd_name, *rest = argv
    handler = COMMANDS.get(cmd_name)
    if not handler:
        print(f"Unknown command: {cmd_name}", file=sys.stderr)
        return 1
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
