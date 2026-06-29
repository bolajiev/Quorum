#!/usr/bin/env bash
# Deploy Quorum backend + frontend to an Alibaba Cloud ECS instance.
# Usage: ECS_HOST=<ip> ECS_USER=root bash infra/deploy_ecs.sh
set -euo pipefail

ECS_HOST="${ECS_HOST:?Set ECS_HOST to your ECS public IP}"
ECS_USER="${ECS_USER:-root}"
REMOTE_DIR="/opt/quorum"

echo "==> Syncing repo to $ECS_USER@$ECS_HOST:$REMOTE_DIR"
rsync -az --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.env' \
  "$(git rev-parse --show-toplevel)/" \
  "$ECS_USER@$ECS_HOST:$REMOTE_DIR/"

echo "==> Uploading .env"
scp "$(git rev-parse --show-toplevel)/.env" "$ECS_USER@$ECS_HOST:$REMOTE_DIR/.env"

echo "==> Installing dependencies and starting service"
ssh "$ECS_USER@$ECS_HOST" bash <<'REMOTE'
set -euo pipefail
cd /opt/quorum/backend
pip3 install -q -r requirements.txt

# Write systemd unit if it doesn't exist
if [ ! -f /etc/systemd/system/quorum.service ]; then
cat > /etc/systemd/system/quorum.service <<'UNIT'
[Unit]
Description=Quorum API
After=network.target

[Service]
WorkingDirectory=/opt/quorum/backend
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 80
Restart=always
EnvironmentFile=/opt/quorum/.env

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable quorum
fi

systemctl restart quorum
systemctl --no-pager status quorum | head -5
echo "==> Quorum running on http://$HOSTNAME:8000"
REMOTE
