#!/usr/bin/env bash
# Reads the Secrets Manager secret review-master/prod (JSON) and writes /etc/review-master.env
set -euo pipefail

AWS_REGION="ap-south-1"
SECRET_ID="review-master/prod"
ENV_FILE="/etc/review-master.env"

echo "[load-secrets] Fetching secret ${SECRET_ID}..."

aws secretsmanager get-secret-value \
  --secret-id "${SECRET_ID}" \
  --region "${AWS_REGION}" \
  --query "SecretString" \
  --output text \
| python3 -c "
import json, sys
for k, v in json.load(sys.stdin).items():
    print(f'{k}={v}')
" > "${ENV_FILE}"

chmod 600 "${ENV_FILE}"
echo "[load-secrets] Written ${ENV_FILE} ($(wc -l < "${ENV_FILE}") vars)"
