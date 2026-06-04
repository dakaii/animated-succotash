from __future__ import annotations

from ..util import require_tools, pulumi_output, run


def cmd_health(_: list[str]) -> int:
    require_tools("gcloud")

    zone = pulumi_output("zone")
    instance = pulumi_output("instance_name")
    project = pulumi_output("project_id")

    print("=== Hermes health check ===\n")
    print(f"Instance: {instance} ({zone})")

    status = run([
        "gcloud", "compute", "instances", "describe", instance,
        "--zone", zone, "--project", project,
        "--format=value(status)",
    ], capture=True)
    print(f"VM status: {status.stdout.strip() or 'unknown'}")

    print("\nRemote bootstrap status:")
    remote = run([
        "gcloud", "compute", "ssh", instance,
        "--zone", zone, "--project", project,
        "--tunnel-through-iap", "--quiet",
        "--command", "test -f /var/lib/hermes/bootstrapped && echo OK || echo PENDING",
    ], capture=True)
    print(remote.stdout.strip() or remote.stderr.strip())

    print("\nHermes doctor:")
    doctor = run([
        "gcloud", "compute", "ssh", instance,
        "--zone", zone, "--project", project,
        "--tunnel-through-iap", "--quiet",
        "--command", "docker exec hermes hermes doctor 2>&1 || true",
    ], capture=True)
    print(doctor.stdout.strip() or doctor.stderr.strip())

    try:
        url = pulumi_output("public_url")
        print(f"\nPublic URL: {url}")
    except RuntimeError:
        print("\nPublic URL: (none — polling mode)")

    return 0
