from __future__ import annotations

from ..util import require_tools, pulumi_output, run


def cmd_rebootstrap(_: list[str]) -> int:
    require_tools("gcloud")

    zone = pulumi_output("zone")
    instance = pulumi_output("instance_name")
    project = pulumi_output("project_id")

    print(f"Re-running bootstrap on {instance}...")
    result = run([
        "gcloud", "compute", "ssh", instance,
        "--zone", zone, "--project", project,
        "--tunnel-through-iap", "--quiet",
        "--command",
        "sudo rm -f /var/lib/hermes/bootstrapped && "
        "sudo PYTHONPATH=/opt/hermes-bundle python3 -B -m bootstrap",
    ])
    return result.returncode


def cmd_tunnel_url(_: list[str]) -> int:
    try:
        url = pulumi_output("public_url")
        print(url)
        return 0
    except RuntimeError:
        pass

    require_tools("gcloud")

    zone = pulumi_output("zone")
    instance = pulumi_output("instance_name")
    project = pulumi_output("project_id")

    result = run([
        "gcloud", "compute", "ssh", instance,
        "--zone", zone, "--project", project,
        "--tunnel-through-iap", "--quiet",
        "--command", "cat /var/log/hermes/tunnel-url.txt 2>/dev/null || true",
    ], capture=True)
    url = result.stdout.strip()
    if url:
        print(url)
    else:
        print("No tunnel URL found (named tunnel or polling mode?)")
    return 0
