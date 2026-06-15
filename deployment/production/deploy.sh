#!/bin/bash
# GoMuseum 生产部署脚本：本机执行，rsync 到 VPS 后远程构建启动
# 用法: ./deploy.sh [ssh_key_path]
set -euo pipefail
VPS=root@38.242.207.219
KEY=${1:-$HOME/.ssh/deepmeeting_deploy}
SSH="ssh -i $KEY -o BatchMode=yes"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> 同步代码到 VPS /opt/gomuseum"
rsync -az --delete -e "$SSH" \
  --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude 'htmlcov' --exclude '.coverage' --exclude 'tts_cache' \
  --exclude 'backend.log' \
  "$REPO_ROOT/backend" "$VPS:/opt/gomuseum/"
rsync -az -e "$SSH" \
  "$REPO_ROOT/deployment/production/docker-compose.yml" \
  "$REPO_ROOT/deployment/production/backup.sh" \
  "$REPO_ROOT/deployment/production/env.production.example" \
  "$VPS:/opt/gomuseum/deploy/"

echo "==> 远程构建并启动"
$SSH $VPS 'cd /opt/gomuseum/deploy && \
  if [ ! -f .env ]; then echo "ERROR: /opt/gomuseum/deploy/.env 不存在，请先基于 env.production.example 创建"; exit 1; fi && \
  docker compose build && docker compose up -d && docker compose ps'

echo "==> 健康检查"
sleep 8
$SSH $VPS 'curl -sf http://127.0.0.1:8100/api/health/ && echo " <- health OK"'
