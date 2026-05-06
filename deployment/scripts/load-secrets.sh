#!/usr/bin/env bash
# Reads all SSM params under /review-master/prod/ and writes /etc/review-master.env
# SSM path convention: /review-master/prod/<ENV_VAR_NAME>
# e.g. /review-master/prod/DJANGO_SECRET_KEY -> DJANGO_SECRET_KEY=<value>
set -euo pipefail

AWS_REGION="ap-south-1"
PARAM_PATH="/review-master/prod"
ENV_FILE="/etc/review-master.env"

echo "[load-secrets] Fetching SSM parameters from ${PARAM_PATH}..."

# Fetch all params, output as tab-separated Name<TAB>Value lines
aws ssm get-parameters-by-path \
  --path "${PARAM_PATH}" \
  --with-decryption \
  --recursive \
  --region "${AWS_REGION}" \
  --query "Parameters[*].[Name,Value]" \
  --output text \
| while IFS=$'\t' read -r name value; do
    # Strip prefix to get env var name: /review-master/prod/DJANGO_SECRET_KEY -> DJANGO_SECRET_KEY
    key="${name#${PARAM_PATH}/}"
    printf '%s=%s\n' "${key}" "${value}"
  done > "${ENV_FILE}"

chmod 600 "${ENV_FILE}"
echo "[load-secrets] Written ${ENV_FILE} ($(wc -l < "${ENV_FILE}") vars)"
