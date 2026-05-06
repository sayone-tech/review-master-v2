#!/usr/bin/env bash
# Runs on EC2 via SSM Run Command on every GitHub Actions deploy.
# Also safe to run manually for ad-hoc deploys.
set -euo pipefail

AWS_REGION="ap-south-1"
APP_DIR="/opt/review-master"
COMPOSE_FILE="${APP_DIR}/docker-compose.prod.yml"

ECR_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${ECR_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Export so Docker Compose variable interpolation (${ECR_IMAGE} in image: field)
# resolves correctly. env_file only injects vars INTO containers — it never
# reaches Compose's own substitution step.
export ECR_IMAGE="${ECR_REGISTRY}/review-master/app:latest"

echo "[deploy] Starting at $(date)"
echo "[deploy] Image: ${ECR_IMAGE}"

# 1. ECR login (instance profile — no hardcoded keys)
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# 2. Refresh secrets: SSM -> /etc/review-master.env
"${APP_DIR}/scripts/load-secrets.sh"

# 3. Pull latest image
docker compose -f "${COMPOSE_FILE}" pull

# 4. Run migrations
docker compose -f "${COMPOSE_FILE}" run --rm web \
  python manage.py migrate --noinput

# 5. Collect static files to S3 (instance profile provides credentials)
docker compose -f "${COMPOSE_FILE}" run --rm web \
  python manage.py collectstatic --noinput --clear

# 6. Restart all services
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

# 7. Wait for web healthcheck (max 2 min)
echo "[deploy] Waiting for web to become healthy..."
for i in $(seq 1 24); do
  if docker compose -f "${COMPOSE_FILE}" exec -T web \
       curl -fsS http://localhost:8000/healthz/ > /dev/null 2>&1; then
    echo "[deploy] Web healthy after $((i * 5))s"
    break
  fi
  if [ "${i}" -eq 24 ]; then
    echo "[deploy] ERROR: web did not become healthy in 120s"
    docker compose -f "${COMPOSE_FILE}" logs --tail=50 web
    exit 1
  fi
  sleep 5
done

echo "[deploy] Done at $(date)"
