[Unit]
Description=Cloudflare quick tunnel for Hermes
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:__TUNNEL_PORT__ --protocol http2 --loglevel info
Restart=always
RestartSec=10
StandardOutput=append:/var/log/hermes/cloudflared.log
StandardError=append:/var/log/hermes/cloudflared.log

[Install]
WantedBy=multi-user.target
