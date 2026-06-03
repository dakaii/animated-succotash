"""Deploy Hermes Agent to a private GCP VM with Secret Manager-backed config."""

from pathlib import Path

import pulumi
import pulumi_gcp as gcp

config = pulumi.Config()
gcp_config = pulumi.Config("gcp")
hermes_config = pulumi.Config("hermes")

project_id = gcp_config.require("project")
zone = gcp_config.get("zone") or "us-central1-a"
region = zone.rsplit("-", 1)[0]

instance_type = hermes_config.get("instance_type") or "e2-medium"
disk_size_gb = hermes_config.get_int("disk_size_gb") or 20
model = hermes_config.get("model") or "deepseek/deepseek-chat"
enable_tunnel = hermes_config.get_bool("enable_cloudflare_tunnel")
if enable_tunnel is None:
    enable_tunnel = True

telegram_webhook = hermes_config.get_bool("telegram_webhook")
if telegram_webhook is None:
    telegram_webhook = False

secret_names = {
    "openrouter-api-key": config.require_secret("openrouter_api_key"),
    "telegram-bot-token": config.require_secret("telegram_bot_token"),
    "telegram-allowed-users": config.require_secret("telegram_allowed_users"),
    "github-pat": config.require_secret("github_pat"),
}

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

data_disk = gcp.compute.Disk(
    "hermes-data",
    type="pd-ssd",
    size=disk_size_gb,
    zone=zone,
)

startup_script_path = Path(__file__).parent.parent / "vm" / "startup.sh"
startup_script = startup_script_path.read_text()
startup_script = startup_script.replace("__PROJECT_ID__", project_id)
startup_script = startup_script.replace("__MODEL__", model)
startup_script = startup_script.replace(
    "__ENABLE_CLOUDFLARE_TUNNEL__", "true" if enable_tunnel else "false"
)
startup_script = startup_script.replace(
    "__TELEGRAM_WEBHOOK__", "true" if telegram_webhook else "false"
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
    network_interfaces=[
        {
            "subnetwork": subnet.id,
        }
    ],
    service_account={
        "email": service_account.email,
        "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
    },
    metadata_startup_script=startup_script,
    allow_stopping_for_update=True,
)

pulumi.export("project_id", project_id)
pulumi.export("zone", zone)
pulumi.export("vm_name", instance.name)
pulumi.export("vm_internal_ip", instance.network_interfaces[0].network_ip)
pulumi.export("ssh_command", pulumi.Output.concat(
    "gcloud compute ssh ", instance.name, " --zone=", zone, " --tunnel-through-iap --project=", project_id
))
pulumi.export("tunnel_url_command", pulumi.Output.concat(
    "gcloud compute ssh ", instance.name, " --zone=", zone, " --tunnel-through-iap --project=", project_id,
    " --command='sudo cat /var/log/hermes/tunnel-url.txt 2>/dev/null || echo Tunnel URL not ready yet'",
))
pulumi.export("hermes_logs_command", pulumi.Output.concat(
    "gcloud compute ssh ", instance.name, " --zone=", zone, " --tunnel-through-iap --project=", project_id,
    " --command='sudo docker logs hermes --tail 50'",
))
