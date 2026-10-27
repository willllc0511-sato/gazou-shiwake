#!/bin/bash
# ConoHa のサーバーへ置く（/opt/gazou-shiwake・127.0.0.1:8610・nginx の gazou）。ほかのサービスには触らない
set -euo pipefail
cd "$(dirname "$0")/.."
H=${1:-conoha_radar}
rsync -a --delete --exclude secrets --exclude model --exclude .git --exclude '__pycache__' --exclude '*.db' ./ "$H:/opt/gazou-shiwake/"
ssh "$H" 'cd /opt/gazou-shiwake && deploy/make_secrets.sh && APP_PORT=8610 docker compose up -d --build 2>&1 | tail -3'
ssh "$H" 'for i in $(seq 1 60); do curl -sf 127.0.0.1:8610/healthz >/dev/null && echo "起動しました" && exit 0; sleep 2; done; echo "起動しない"; exit 1'
