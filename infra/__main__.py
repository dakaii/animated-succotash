"""Deploy Hermes Agent to a private GCP VM with Secret Manager-backed config."""

import base64
import secrets

import pulumi
import pulumi_cloudflare as cloudflare
import pulumi_gcp as gcp

config = pulumi.Config()
gcp_config = pulumi.Config("gcp")
hermes_config = pulumi.Config("hermes")
cloudflare_config = pulumi.Config("cloudflare")

project_id = gcp_config.require("project")
zone = gcp_config.get("zone") or "us-central1-a"
region = zone.rsplit("-", 1)[0]

instance_type = hermes_config.get("instance_type") or "e2-medium"
disk_size_gb = hermes_config.get_int("disk_size_gb") or 20
model = hermes_config.get("model") or "deepseek/deepseek-chat"

ingress_mode = hermes_config.get("ingress_mode") or hermes_config.get("tunnel_mode") or "cloudflare-named"
if ingress_mode in ("named", "quick", "disabled"):
    ingress_mode = {
        "named": "cloudflare-named",
        "quick": "cloudflare-quick",
        "disabled": "none",
    }[ingress_mode]

valid_ingress = ("cloudflare-named", "cloudflare-quick", "none")
if ingress_mode not in valid_ingress:
    raise ValueError(f"hermes:ingress_mode must be one of {valid_ingress}")

telegram_webhook = hermes_config.get_bool("telegram_webhook")
if telegram_webhook is None:
    telegram_webhook = ingress_mode == "cloudflare-named"

public_hostname = hermes_config.get("hostname") or cloudflare_config.get("hostname") or ""

for api in (
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "monitoring.googleapis.com",
):
    gcp.projects.Service(
        f"enable-{api.replace('.', '-')}",
        service=api,
        disable_on_destroy=False,
    )

secret_names = {
    "openrouter-api-key": config.require_secret("openrouter_api_key"),
    "telegram-bot-token": config.require_secret("telegram_bot_token"),
    "telegram-allowed-users": config.require_secret("telegram_allowed_users"),
}

github_pat = config.get_secret("github_pat")
if github_pat:
    secret_names["github-pat"] = github_pat

if ingress_mode == "cloudflare-named":
    account_id = cloudflare_config.require("account_id")
    zone_id = cloudflare_config.require("zone_id")
    public_hostname = public_hostname or cloudflare_config.require("hostname")

    tunnel_secret = cloudflare_config.get_secret("tunnel_secret")
    if not tunnel_secret:
        tunnel_secret = base64.b64encode(secrets.token_bytes(32)).decode()

    tunnel = cloudflare.ZeroTrustTunnelCloudflared(
        "hermes-tunnel",
        account_id=account_id,
        name="hermes-agent",
        config_src="cloudflare",
        tunnel_secret=tunnel_secret,
    )

    service_port = "8443" if telegram_webhook else "9119"
    cloudflare.ZeroTrustTunnelCloudflaredConfig(
        "hermes-tunnel-config",
        account_id=account_id,
        tunnel_id=tunnel.id,
        config={
            "ingresses": [
                {
                    "hostname": public_hostname,
                    "service": f"http://127.0.0.1:{service_port}",
                    "origin_request": {
                        "no_tls_verify": True,
                        "http2_origin": True,
                    },
                },
                {"service": "http_status:404"},
            ],
        },
    )

    cloudflare.Record(
        "hermes-tunnel-dns",
        zone_id=zone_id,
        name=public_hostname.split(".")[0],
        type="CNAME",
        content=tunnel.id.apply(lambda tid: f"{tid}.cfargotunnel.com"),
        proxied=True,
        ttl=1,
    )

    tunnel_token = cloudflare.get_zero_trust_tunnel_cloudflared_token_output(
        account_id=account_id,
        tunnel_id=tunnel.id,
    )
    secret_names["cloudflare-tunnel-token"] = tunnel_token.token

secrets = {}
for secret_id, secret_value in secret_names.items():
    secret = gcp.secretmanager.Secret(
        f"hermes-{secret_id}",
        secret_id=secret_id,
        replication={"auto": {}},
    )
    gcp.secretmanager.SecretVersion(
        f"hermes-{secret_id}-version",
        secret=secret.id,
        secret_data=secret_value,
    )
    secrets[secret_id] = secret

network = gcp.compute.Network(
    "hermes-vpc",
    auto_create_subnetworks=False,
    routing_mode="REGIONAL",
)

subnet = gcp.compute.Subnetwork(
    "hermes-subnet",
    ip_cidr_range="10.0.0.0/24",
    network=network.id,
    region=region,
    private_ip_google_access=True,
)

router = gcp.compute.Router(
    "hermes-router",
    network=network.id,
    region=region,
)

gcp.compute.RouterNat(
    "hermes-nat",
    router=router.name,
    region=region,
    nat_ip_allocate_option="AUTO_ONLY",
    source_subnetwork_ip_ranges_to_nat="LIST_OF_SUBNETWORKS",
    subnetworks=[
        {
            "name": subnet.id,
            "source_ip_ranges_to_nat": ["ALL_IP_RANGES"],
        }
    ],
)

gcp.compute.Firewall(
    "hermes-allow-iap-ssh",
    network=network.id,
    allows=[{"protocol": "tcp", "ports": ["22"]}],
    source_ranges=["35.235.240.0/20"],
    target_tags=["hermes"],
)

service_account = gcp.serviceaccount.Account(
    "hermes-sa",
    account_id="hermes-agent",
    display_name="Hermes Agent VM",
)

for secret_id, secret in secrets.items():
    gcp.secretmanager.SecretIamMember(
        f"hermes-{secret_id}-accessor",
        secret_id=secret.id,
        role="roles/secretmanager.secretAccessor",
        member=pulumi.Output.concat("serviceAccount:", service_account.email),
    )

gcp.projects.IAMMember(
    "hermes-sa-log-writer",
    project=project_id,
    role="roles/logging.logWriter",
    member=pulumi.Output.concat("serviceAccount:", service_account.email),
)

from monitoring import create_weekly_snapshot_policy, setup_monitoring

snapshot_policy = create_weekly_snapshot_policy(region)

data_disk = gcp.compute.Disk(
    "hermes-data",
    type="pd-ssd",
    size=disk_size_gb,
    zone=zone,
    resource_policies=[snapshot_policy.id],
)

from vm_bundle import build_startup_script

startup_script = build_startup_script(
    project_id=project_id,
    model=model,
    ingress_mode=ingress_mode,
    public_hostname=public_hostname,
    telegram_webhook=telegram_webhook,
)

instance = gcp.compute.Instance(
    "hermes-vm",
    name="hermes-vm",
    machine_type=instance_type,
    zone=zone,
    tags=["hermes"],
    boot_disk={
        "initialize_params": {
            "image": "ubuntu-os-cloud/ubuntu-2404-lts-amd64",
            "size": 30,
        }
    },
    attached_disks=[
        {
            "source": data_disk.id,
            "device_name": "hermes-data",
            "mode": "READ_WRITE",
        }
    ],
    network_interfaces=[{"subnetwork": subnet.id}],
    service_account={
        "email": service_account.email,
        "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
    },
    metadata_startup_script=startup_script,
    allow_stopping_for_update=True,
)

alert_email = hermes_config.get("alert_email") or ""
budget_usd = hermes_config.get_float("budget_usd") or 50.0
billing_account = gcp_config.get("billing_account") or ""

if billing_account:
    gcp.projects.Service(
        "enable-billingbudgets-googleapis-com",
        service="billingbudgets.googleapis.com",
        disable_on_destroy=False,
    )

setup_monitoring(
    project_id=project_id,
    public_hostname=public_hostname if ingress_mode != "none" else "",
    alert_email=alert_email,
    billing_account=billing_account,
    budget_usd=budget_usd,
)

pulumi.export("project_id", project_id)
pulumi.export("zone", zone)
pulumi.export("vm_name", instance.name)
pulumi.export("instance_name", instance.name)
pulumi.export("vm_internal_ip", instance.network_interfaces[0].network_ip)
pulumi.export("ingress_mode", ingress_mode)
pulumi.export("telegram_webhook", telegram_webhook)
if public_hostname:
    pulumi.export("public_url", f"https://{public_hostname}")
    if telegram_webhook:
        pulumi.export("telegram_webhook_url", f"https://{public_hostname}/telegram")
pulumi.export(
    "ssh_command",
    pulumi.Output.concat(
        "gcloud compute ssh ",
        instance.name,
        " --zone=",
        zone,
        " --tunnel-through-iap --project=",
        project_id,
    ),
)
pulumi.export(
    "tunnel_url_command",
    pulumi.Output.concat(
        "gcloud compute ssh ",
        instance.name,
        " --zone=",
        zone,
        " --tunnel-through-iap --project=",
        project_id,
        " --command='sudo cat /var/log/hermes/tunnel-url.txt 2>/dev/null || echo URL not ready yet'",
    ),
)
pulumi.export(
    "hermes_logs_command",
    pulumi.Output.concat(
        "gcloud compute ssh ",
        instance.name,
        " --zone=",
        zone,
        " --tunnel-through-iap --project=",
        project_id,
        " --command='sudo docker logs hermes --tail 50'",
    ),
)
