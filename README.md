# Hermes Agent on GCP

Deploy [Hermes Agent](https://github.com/NousResearch/hermes-agent) to a private GCP VM with:

- **Pulumi** — VPC, NAT, Secret Manager, persistent disk, VM
- **Telegram** — message your agent (polling mode, no public URL needed)
- **GitHub MCP** — issues, PRs, code search, file edits
- **Cloudflare quick tunnel** — free `*.trycloudflare.com` URL for the dashboard (optional)

## Architecture

```
Telegram App
    │  (outbound polling — VM initiates connection)
    ▼
Hermes Gateway (Docker on private GCP VM)
    ├── OpenRouter → DeepSeek
    ├── GitHub MCP → your repos
    └── Cloudflare quick tunnel → dashboard (optional)
```

The VM has **no public IP**. Outbound traffic goes through Cloud NAT. Telegram works via long polling, so you never need to SSH for daily use.

## Prerequisites

- [Pulumi CLI](https://www.pulumi.com/docs/install/)
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) (authenticated)
- [Docker](https://docs.docker.com/get-docker/) (for local dev only)
- OpenRouter API key ([openrouter.ai](https://openrouter.ai))
- Telegram bot token ([@BotFather](https://t.me/BotFather))
- Telegram user ID ([@userinfobot](https://t.me/userinfobot))
- GitHub fine-grained PAT (Contents + Pull requests read/write)

## Quick start

### 1. Configure secrets

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

This stores secrets in Pulumi config and provisions them in GCP Secret Manager on deploy.

### 2. Deploy to GCP

```bash
cd infra
pulumi up
```

First boot takes ~3–5 minutes (Docker pull + Hermes start).

### 3. Message your bot

Open Telegram, find your bot, send a message. Hermes replies via the gateway running on the VM.

### 4. (Optional) Open the dashboard

```bash
./scripts/get-tunnel-url.sh
```

Returns a `https://….trycloudflare.com` URL for the Hermes dashboard. The URL stays stable as long as the tunnel process keeps running (systemd auto-restarts it).

## Local development

Test Hermes on your machine before deploying:

```bash
cp hermes/.env.example hermes/.env
# Edit hermes/.env with your keys

cp hermes/config.yaml.example hermes/config.yaml
# Replace GITHUB_PERSONAL_ACCESS_TOKEN in config.yaml

./scripts/local-dev.sh
```

## Project layout

```
animated-succotash/
├── infra/                  # Pulumi GCP infrastructure
│   ├── __main__.py
│   ├── Pulumi.yaml
│   └── requirements.txt
├── vm/
│   └── startup.sh          # VM bootstrap (Docker, Hermes, cloudflared)
├── hermes/
│   ├── docker-compose.yml  # Local dev compose file
│   ├── config.yaml.example
│   └── .env.example
└── scripts/
    ├── setup.sh            # Interactive Pulumi config
    ├── deploy.sh           # pulumi up wrapper
    ├── local-dev.sh        # Run Hermes locally
    ├── health.sh           # Check VM + gateway status
    ├── get-tunnel-url.sh   # Fetch dashboard URL from VM
    └── rebootstrap.sh      # Re-run bootstrap after secret changes
```

## Configuration

| Pulumi key | Default | Description |
|---|---|---|
| `gcp:project` | — | GCP project ID |
| `gcp:zone` | `us-central1-a` | VM zone |
| `hermes:instance_type` | `e2-medium` | VM size (use `e2-micro` for free tier) |
| `hermes:model` | `deepseek/deepseek-chat` | OpenRouter model |
| `hermes:enable_cloudflare_tunnel` | `true` | Expose dashboard via quick tunnel |
| `hermes:telegram_webhook` | `false` | Use webhook instead of polling |

Secrets (set with `pulumi config set --secret`):

| Key | Description |
|---|---|
| `openrouter_api_key` | OpenRouter API key |
| `telegram_bot_token` | From @BotFather |
| `telegram_allowed_users` | Your numeric Telegram user ID |
| `github_pat` | GitHub PAT for MCP server |

## GitHub MCP scopes

Create a fine-grained PAT limited to your repos:

- Contents: Read and write
- Pull requests: Read and write
- Issues: Read and write (optional)

The VM config enables these MCP tools: list/create/update issues, search code, read/write files, create/review PRs.

## Cost estimate

| Resource | Monthly |
|---|---|
| e2-medium VM | ~$15–20 |
| 20GB SSD disk | ~$2 |
| Cloudflare quick tunnel | $0 |
| OpenRouter (DeepSeek Flash) | ~$2–5 |
| **Total** | **~$17–27** |

Use `e2-micro` + GCP free tier to reduce VM cost to $0 for 12 months.

## Troubleshooting

**Bot not responding**

```bash
# SSH via IAP (only when debugging)
pulumi stack output ssh_command | bash
sudo docker logs hermes --tail 100
sudo docker exec hermes hermes gateway status
```

**Check startup logs**

```bash
gcloud compute ssh hermes-vm --zone=us-central1-a --tunnel-through-iap \
  --command='sudo tail -100 /var/log/hermes/startup.log'
```

**Re-run bootstrap after secret rotation**

```bash
./scripts/rebootstrap.sh
```

## Telegram: polling vs webhook

Default is **polling** (recommended for always-on GCP VMs). The VM connects outbound to Telegram — no tunnel or domain required.

Enable webhook mode only if you need sleep-when-idle (e.g. serverless):

```bash
pulumi config set hermes:telegram_webhook true
pulumi up
```

This requires the Cloudflare tunnel URL to be ready before Hermes starts.
