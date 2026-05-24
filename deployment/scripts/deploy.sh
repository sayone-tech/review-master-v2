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

DEPLOY_BUCKET="review-master-static-prod"

# 1. Refresh deploy assets from S3 (which CI just synced from the app repo's
# deployment/ folder). Without this step, compose / scripts / Caddyfile
# changes never reach the running box. Self-modifies this very script —
# safe because bash has already parsed the file before execution begins.
echo "[deploy] Refreshing deploy assets from s3://${DEPLOY_BUCKET}/deploy/"
aws s3 cp "s3://${DEPLOY_BUCKET}/deploy/docker-compose.prod.yml" \
  "${COMPOSE_FILE}"
aws s3 cp "s3://${DEPLOY_BUCKET}/deploy/load-secrets.sh" \
  "${APP_DIR}/scripts/load-secrets.sh"
aws s3 cp "s3://${DEPLOY_BUCKET}/deploy/Caddyfile" \
  "${APP_DIR}/caddy/Caddyfile"
# Pull deploy.sh last so any failures above happen against the version
# already in use, not the new one.
aws s3 cp "s3://${DEPLOY_BUCKET}/deploy/deploy.sh" \
  "${APP_DIR}/scripts/deploy.sh"
chmod +x "${APP_DIR}/scripts/load-secrets.sh" "${APP_DIR}/scripts/deploy.sh"

# 2. ECR login (instance profile — no hardcoded keys)
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# 3. Refresh secrets: Secrets Manager -> /etc/review-master.env
"${APP_DIR}/scripts/load-secrets.sh"

# 4. Pull latest image
docker compose -f "${COMPOSE_FILE}" pull

# 5. Run migrations
docker compose -f "${COMPOSE_FILE}" run --rm web \
  python manage.py migrate --noinput

# 6. Collect static files to S3 (instance profile provides credentials)
docker compose -f "${COMPOSE_FILE}" run --rm web \
  python manage.py collectstatic --noinput --clear

# 7. Restart all services
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

# 8. Wait for web healthcheck (max 2 min)
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
