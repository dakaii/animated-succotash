from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra"


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd or INFRA,
        text=True,
        capture_output=capture,
        input=input_text,
        check=False,
    )


def pulumi_output(key: str, stack: str = "dev") -> str:
    run(["pulumi", "stack", "select", stack], capture=True)
    result = run(["pulumi", "stack", "output", key], capture=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Missing stack output: {key}")
    return result.stdout.strip()


def require_tools(*tools: str) -> None:
    for tool in tools:
        if subprocess.run(["which", tool], capture=True).returncode != 0:
            raise SystemExit(f"Required tool not found: {tool}")
