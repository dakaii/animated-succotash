from __future__ import annotations

import getpass

from ..util import INFRA, require_tools, run


def cmd_setup(_: list[str]) -> int:
    require_tools("pulumi", "gcloud")

    print("=== Hermes GCP setup ===\n")
    project_id = input("GCP project ID: ").strip()
    zone = input("GCP zone [us-central1-a]: ").strip() or "us-central1-a"
    alert_email = input("Alert email (uptime/budget) [optional]: ").strip()

    run(["pulumi", "stack", "init", "dev"], capture=True)
    run(["pulumi", "stack", "select", "dev"], capture=True)
    run(["pulumi", "config", "set", "gcp:project", project_id])
    run(["pulumi", "config", "set", "gcp:zone", zone])
    if alert_email:
        run(["pulumi", "config", "set", "hermes:alert_email", alert_email])

    print("\n=== API keys (stored as Pulumi secrets) ===\n")
    openrouter = getpass.getpass("OpenRouter API key: ")
    telegram_token = getpass.getpass("Telegram bot token: ")
    telegram_user = getpass.getpass("Telegram user ID: ")
    github_pat = getpass.getpass("GitHub PAT (optional, Enter to skip): ")

    run(["pulumi", "config", "set", "--secret", "openrouter_api_key", openrouter])
    run(["pulumi", "config", "set", "--secret", "telegram_bot_token", telegram_token])
    run(["pulumi", "config", "set", "--secret", "telegram_allowed_users", telegram_user])
    if github_pat:
        run(["pulumi", "config", "set", "--secret", "github_pat", github_pat])

    instance_type = input("\nVM size [e2-medium]: ").strip() or "e2-medium"
    model = input("Model [deepseek/deepseek-chat]: ").strip() or "deepseek/deepseek-chat"
    run(["pulumi", "config", "set", "hermes:instance_type", instance_type])
    run(["pulumi", "config", "set", "hermes:model", model])

    print("\n=== Ingress ===")
    print("  cloudflare-named — stable URL (default)")
    print("  cloudflare-quick — random *.trycloudflare.com")
    print("  none             — polling only, no public URL")
    ingress = input("Ingress mode [cloudflare-named]: ").strip() or "cloudflare-named"
    run(["pulumi", "config", "set", "hermes:ingress_mode", ingress])

    if ingress == "cloudflare-named":
        if not __import__("os").environ.get("CLOUDFLARE_API_TOKEN"):
            print("\nSet CLOUDFLARE_API_TOKEN before deploy.")
        cf_account = input("Cloudflare account ID: ").strip()
        cf_zone = input("Cloudflare zone ID: ").strip()
        hostname = input("Hostname (bot.yourdomain.com): ").strip()
        run(["pulumi", "config", "set", "cloudflare:account_id", cf_account])
        run(["pulumi", "config", "set", "cloudflare:zone_id", cf_zone])
        run(["pulumi", "config", "set", "cloudflare:hostname", hostname])
        run(["pulumi", "config", "set", "hermes:hostname", hostname])
        webhook = input("Use Telegram webhooks? [Y/n]: ").strip()
        run([
            "pulumi", "config", "set", "hermes:telegram_webhook",
            "false" if webhook.lower() == "n" else "true",
        ])
    elif ingress == "cloudflare-quick":
        webhook = input("Use Telegram webhooks? [y/N]: ").strip()
        run([
            "pulumi", "config", "set", "hermes:telegram_webhook",
            "true" if webhook.lower() == "y" else "false",
        ])
    else:
        run(["pulumi", "config", "set", "hermes:telegram_webhook", "false"])

    billing = input("\nGCP billing account ID (budget alerts, optional): ").strip()
    if billing:
        run(["pulumi", "config", "set", "gcp:billing_account", billing])

    run(["python3", "-m", "venv", ".venv"], cwd=INFRA, capture=True)
    run([".venv/bin/pip", "install", "-q", "-r", "requirements.txt"], cwd=INFRA)

    run([
        "gcloud", "services", "enable",
        "compute.googleapis.com",
        "secretmanager.googleapis.com",
        "iam.googleapis.com",
        "iap.googleapis.com",
        "monitoring.googleapis.com",
        f"--project={project_id}",
    ])

    print("\nReady. Deploy with: python -m hermes_gcp deploy")
    return 0
