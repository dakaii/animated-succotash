# Hermes Agent on GCP

Deploy [Hermes Agent](https://github.com/NousResearch/hermes-agent) to a private GCP VM with:

- **Pulumi** — VPC, NAT, Secret Manager, persistent disk, VM
- **Telegram** — message your agent (polling mode, no public URL needed)
- **GitHub MCP** — issues, PRs, code search, file edits
- **Cloudflare named tunnel (default)** — stable `https://bot.yourdomain.com`, no open ports

## Ingress options

| Mode | Public IP | Domain | Best for |
|---|---|---|---|
| **`cloudflare-named`** (default) | No | CNAME on Cloudflare | Stable HTTPS URL, private VM |
| **`none`** | No | No | Telegram polling only — simplest |
| **`cloudflare-quick`** | No | Random `*.trycloudflare.com` | Dev/testing only |

For messaging via Telegram, **`none` + polling** is enough — no domain or tunnel required.
Use **`cloudflare-named`** when you want a stable dashboard URL or webhooks.

## Architecture

```
Telegram App
    │  webhook (HTTPS push) or polling (outbound)
    ▼
Hermes Gateway (Docker on private GCP VM)
    ├── OpenRouter → DeepSeek
    ├── GitHub MCP → your repos
    └── Cloudflare named tunnel → bot.yourdomain.com
```

The VM has **no public IP**. Outbound traffic goes through Cloud NAT.

## Domain setup (one-time, ~$10/year)

Yes — you buy a domain **separately**, then point its DNS to Cloudflare (free):

1. Register a domain at [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/), Namecheap, Google Domains, etc. (~$8–15/year)
2. Add the domain to your Cloudflare account (free plan is fine)
3. Use a subdomain like `bot.yourdomain.com` in `./scripts/setup.sh`

Cloudflare Tunnel itself is **$0/month**. You only pay for the domain registration.

## Prerequisites

- [Pulumi CLI](https://www.pulumi.com/docs/install/)
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) (authenticated)
- [Docker](https://docs.docker.com/get-docker/) (for local dev only)
- **Domain on Cloudflare** (for named tunnel — default)
- **Cloudflare API token** with Tunnel Edit + DNS Edit permissions (`export CLOUDFLARE_API_TOKEN=...`)
- OpenRouter API key ([openrouter.ai](https://openrouter.ai))
- Telegram bot token ([@BotFather](https://t.me/BotFather))
- Telegram user ID ([@userinfobot](https://t.me/userinfobot))
- GitHub fine-grained PAT (Contents + Pull requests read/write, optional)

## Quick start

### 1. Configure secrets

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

This stores secrets in Pulumi config and provisions them in GCP Secret Manager on deploy.

### 2. Deploy to GCP

```bash
export CLOUDFLARE_API_TOKEN=your-token   # required for named tunnel
./scripts/deploy.sh
```

First boot takes ~3–5 minutes (Docker pull + Hermes start).

### 3. Message your bot

Open Telegram, find your bot, send a message. Hermes replies via the gateway running on the VM.

### 4. Your stable URL

```bash
./scripts/get-tunnel-url.sh
# e.g. https://bot.yourdomain.com
```

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
├── infra/                  # Pulumi GCP + Cloudflare infrastructure
│   ├── __main__.py
│   ├── vm_bundle.py        # Packages vm/ files into startup metadata
│   └── requirements.txt
├── vm/
│   ├── startup.sh          # Thin entrypoint (env vars → bootstrap)
│   ├── bootstrap.sh        # Orchestrates first-boot setup
│   ├── docker-compose.yml  # Hermes container definition
│   ├── hermes.config.yaml.tpl
│   ├── hermes.github-mcp.yaml.tpl
│   ├── systemd/            # cloudflared unit files
│   └── lib/                # Modular bootstrap functions
├── hermes/                 # Local dev only
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
| `hermes:ingress_mode` | `cloudflare-named` | `cloudflare-named`, `cloudflare-quick`, `none` |
| `hermes:hostname` | — | e.g. `bot.yourdomain.com` |

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
| Cloudflare named tunnel | $0 |
| Domain (annual) | ~$8–15/year |
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

## Telegram: polling vs webhook (not WebSocket)

Telegram bots do **not** use WebSockets. The Bot API only supports two update modes:

| Mode | How it works | Needs public URL? | Best for |
|---|---|---|---|
| **Polling** (long polling) | Your VM repeatedly asks Telegram "any new messages?" | No | Simplest; works without a domain |
| **Webhook** | Telegram pushes messages to your HTTPS URL | Yes | Slightly lower latency; stable URL via named tunnel |

There is no WebSocket option for Telegram bots. Hermes uses one of the above under the hood.

**Default with named tunnel:** webhook mode at `https://bot.yourdomain.com/telegram` — Telegram pushes updates to you instead of your VM polling outbound.

**Prefer polling?** Set `hermes:telegram_webhook false` — works fine on an always-on VM and doesn't need the tunnel for messaging at all.

```bash
pulumi config set hermes:telegram_webhook false
pulumi up
```
