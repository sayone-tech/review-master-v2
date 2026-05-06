#!/usr/bin/env bash
# EC2 first-boot bootstrap — Amazon Linux 2023, Graviton (aarch64)
# Runs once as root via EC2 user-data.
set -euo pipefail

AWS_REGION="ap-south-1"
APP_DIR="/opt/review-master"
LOG_FILE="/var/log/review-master-init.log"

exec > >(tee -a "${LOG_FILE}") 2>&1
echo "[user-data] Starting at $(date)"

# ---------- SSM Agent ----------
dnf install -y amazon-ssm-agent
systemctl enable --now amazon-ssm-agent

# ---------- Docker ----------
dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

# ---------- Docker Compose plugin (aarch64) ----------
COMPOSE_VERSION="2.27.1"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL \
  "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
echo "[user-data] Docker Compose $(docker compose version)"

# ---------- App directory ----------
mkdir -p "${APP_DIR}/scripts" "${APP_DIR}/caddy"

# ---------- Copy deployment files ----------
aws s3 cp "s3://review-master-static-prod/deploy/load-secrets.sh" "${APP_DIR}/scripts/load-secrets.sh" || true
aws s3 cp "s3://review-master-static-prod/deploy/deploy.sh" "${APP_DIR}/scripts/deploy.sh" || true
aws s3 cp "s3://review-master-static-prod/deploy/docker-compose.prod.yml" "${APP_DIR}/docker-compose.prod.yml" || true
aws s3 cp "s3://review-master-static-prod/deploy/Caddyfile" "${APP_DIR}/caddy/Caddyfile" || true
chmod +x "${APP_DIR}/scripts/"*.sh 2>/dev/null || true

# ---------- ECR login ----------
ECR_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS \
    --password-stdin \
    "${ECR_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "[user-data] Done at $(date)"
echo "[user-data] Run '${APP_DIR}/scripts/load-secrets.sh' then deploy.sh to start the app."
