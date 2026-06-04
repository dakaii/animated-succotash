from __future__ import annotations

from ..util import INFRA, require_tools, run


def cmd_deploy(args: list[str]) -> int:
    require_tools("pulumi")
    venv_pulumi = INFRA / ".venv/bin/pulumi"
    cmd = [str(venv_pulumi), "up"] if venv_pulumi.exists() else ["pulumi", "up"]
    cmd.extend(args)
    result = run(cmd, cwd=INFRA)
    if result.returncode == 0:
        print("\nHealth check: python -m hermes_gcp health")
    return result.returncode
