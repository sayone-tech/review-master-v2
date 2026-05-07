# Infrastructure Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Move the app to `app.reviewbee.in`, migrate all secrets from SSM Parameter Store to AWS Secrets Manager, and replace SSH with Session Manager — all rolled out together.

**Architecture:** Terraform manages all infrastructure changes (Route 53, Secrets Manager, IAM, security groups, EC2 key pair removal). The `load-secrets.sh` script on EC2 is rewritten to fetch a single JSON secret from Secrets Manager instead of paginated SSM parameters. Migration is done in two Terraform applies — first to create Secrets Manager and update IAM, then to delete SSM after verifying the new setup works.

**Tech Stack:** Terraform, AWS Secrets Manager, AWS Systems Manager Session Manager, Caddy, GitHub Actions

---

## File Map

| File | Change |
|------|--------|
| `deployment/terraform/secrets.tf` | New — replaces ssm.tf, creates Secrets Manager secret |
| `deployment/terraform/ssm.tf` | Deleted in Task 5 |
| `deployment/terraform/iam.tf` | EC2 role: swap SSM perms → Secrets Manager + managed policy; GitHub Actions role: swap ssm:GetParameter → secretsmanager:GetSecretValue |
| `deployment/terraform/route53.tf` | Add A record for `app.reviewbee.in` |
| `deployment/terraform/ec2.tf` | Remove key_pair resource and key_name from instance |
| `deployment/terraform/security_groups.tf` | Remove SSH ingress rule |
| `deployment/terraform/variables.tf` | Remove operator_ip variable |
| `deployment/terraform/terraform.tfvars` | Remove operator_ip value |
| `deployment/scripts/load-secrets.sh` | Rewrite to fetch from Secrets Manager |
| `.github/workflows/deploy.yml` | Update smoke test to use Secrets Manager |

---

### Task 1: Create Secrets Manager secret (Terraform)

**Files:**
- Create: `deployment/terraform/secrets.tf`

- [x] **Step 1: Create `deployment/terraform/secrets.tf`**

```hcl
resource "aws_secretsmanager_secret" "app" {
  name        = "review-master/prod"
  description = "All production environment variables for review-master"

  tags = { Project = "review-master" }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DJANGO_SECRET_KEY               = "CHANGE_ME_run_get_random_secret_key"
    DJANGO_ALLOWED_HOSTS            = "app.reviewbee.in"
    SITE_URL                        = "https://app.reviewbee.in"
    DATABASE_URL                    = "postgres://reviewbee:CHANGE_ME@CHANGE_ME_rds_endpoint:5432/reviewmaster"
    REDIS_URL                       = "redis://redis:6379"
    GOOGLE_OAUTH_CLIENT_ID          = "CHANGE_ME"
    GOOGLE_OAUTH_CLIENT_SECRET      = "CHANGE_ME"
    GOOGLE_OAUTH_REDIRECT_URI       = "https://app.reviewbee.in/oauth/google/callback/"
    FERNET_SALT_KEY                 = "CHANGE_ME_generate_fernet_key"
    OPENAI_API_KEY                  = "CHANGE_ME"
    OPENAI_MODEL                    = "gpt-4o-mini-2024-07-18"
    OPENAI_MAX_RETRIES              = "3"
    ENRICHMENT_BATCH_SIZE           = "10"
    LANGSMITH_API_KEY               = "CHANGE_ME"
    LANGSMITH_PROJECT               = "review-platform-production"
    LANGSMITH_ENDPOINT              = "https://api.smith.langchain.com"
    SENTRY_DSN                      = "CHANGE_ME"
    ENVIRONMENT                     = "production"
    EMAIL_PROVIDER                  = "resend"
    RESEND_API_KEY                  = "CHANGE_ME"
    DEFAULT_FROM_EMAIL              = "noreply@reviewbee.in"
    DEFAULT_REPLY_TO                = "support@reviewbee.in"
    AWS_STORAGE_BUCKET_NAME         = "review-master-static-prod"
    AWS_S3_REGION_NAME              = "ap-south-1"
    CADDY_DOMAIN                    = "app.reviewbee.in"
    CADDY_ACME_EMAIL                = "renjith@sayonetech.com"
    INITIAL_SYNC_PAGE_SIZE          = "50"
    INCREMENTAL_SYNC_INTERVAL_HOURS = "6"
    INCREMENTAL_SYNC_JITTER_MINUTES = "30"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
```

- [x] **Step 2: Verify the file is valid HCL**

Run from `deployment/terraform/`:
```bash
terraform validate
```
Expected: `Success! The configuration is valid.`

- [x] **Step 3: Commit**

```bash
git add deployment/terraform/secrets.tf
git commit -m "feat(terraform): add Secrets Manager secret for all app env vars"
```

---

### Task 2: Add Route 53 record for `app.reviewbee.in`

**Files:**
- Modify: `deployment/terraform/route53.tf`

- [x] **Step 1: Add the `app` subdomain A record**

Open `deployment/terraform/route53.tf` and add after the existing `www` record:

```hcl
resource "aws_route53_record" "app" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "app.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.ec2.public_ip]
}
```

- [x] **Step 2: Validate**

```bash
terraform validate
```
Expected: `Success! The configuration is valid.`

- [x] **Step 3: Commit**

```bash
git add deployment/terraform/route53.tf
git commit -m "feat(terraform): add Route 53 A record for app.reviewbee.in"
```

---

### Task 3: Update IAM — EC2 and GitHub Actions roles

**Files:**
- Modify: `deployment/terraform/iam.tf`

This task does three things to `iam.tf`:
1. EC2 role: remove SSM parameter read + KMS statements, replace with Secrets Manager read + `AmazonSSMManagedInstanceCore` managed policy
2. EC2 role: remove manual `ssmmessages:*` statements (covered by the managed policy)
3. GitHub Actions role: remove `ssm:GetParameter`, add `secretsmanager:GetSecretValue`

- [x] **Step 1: Replace EC2 SSM parameter + KMS statements with Secrets Manager**

In `deployment/terraform/iam.tf`, find and replace the SSM and KMS blocks in `data.aws_iam_policy_document.ec2_permissions`:

Remove these two statements:
```hcl
  # SSM — read secrets under /review-master/prod/
  statement {
    actions = [
      "ssm:GetParametersByPath",
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:*:parameter/review-master/prod*",
    ]
  }

  # KMS — decrypt SecureString params (default SSM KMS key)
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${var.aws_region}:*:key/alias/aws/ssm"]
  }
```

Replace with:
```hcl
  # Secrets Manager — read all app env vars
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:${var.aws_region}:*:secret:review-master/prod*"]
  }
```

- [x] **Step 2: Remove manual ssmmessages statements from EC2 role**

In `data.aws_iam_policy_document.ec2_permissions`, remove this entire statement block:
```hcl
  # SSM Agent — required for SSM Run Command to reach the instance
  statement {
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
      "ssm:UpdateInstanceInformation",
    ]
    resources = ["*"]
  }
```

- [x] **Step 3: Attach AmazonSSMManagedInstanceCore managed policy to EC2 role**

After the `aws_iam_role_policy.ec2` resource, add:
```hcl
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
```

- [x] **Step 4: Update GitHub Actions role — swap SSM for Secrets Manager**

In `data.aws_iam_policy_document.github_permissions`, remove:
```hcl
  # SSM — read parameters for smoke test (CADDY_DOMAIN)
  statement {
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:*:parameter/review-master/prod/*"]
  }
```

Add:
```hcl
  # Secrets Manager — read domain for smoke test
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:${var.aws_region}:*:secret:review-master/prod*"]
  }
```

- [x] **Step 5: Validate**

```bash
terraform validate
```
Expected: `Success! The configuration is valid.`

- [x] **Step 6: Commit**

```bash
git add deployment/terraform/iam.tf
git commit -m "feat(terraform): swap SSM perms for Secrets Manager on EC2 and GitHub Actions roles"
```

---

### Task 4: Remove SSH — security group, key pair, variables

**Files:**
- Modify: `deployment/terraform/security_groups.tf`
- Modify: `deployment/terraform/ec2.tf`
- Modify: `deployment/terraform/variables.tf`
- Modify: `deployment/terraform/terraform.tfvars`

- [x] **Step 1: Remove SSH ingress rule from security group**

In `deployment/terraform/security_groups.tf`, remove the entire SSH ingress block and update the description:

Change:
```hcl
resource "aws_security_group" "ec2" {
  name        = "review-master-ec2"
  description = "Review Master EC2 - HTTP/HTTPS public, SSH operator-only"
```

To:
```hcl
resource "aws_security_group" "ec2" {
  name        = "review-master-ec2"
  description = "Review Master EC2 - HTTP/HTTPS public only"
```

Remove the SSH ingress block entirely:
```hcl
  ingress {
    description = "SSH - operator IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.operator_ip]
  }
```

- [x] **Step 2: Remove key pair resource and key_name from EC2 instance**

In `deployment/terraform/ec2.tf`, remove:
```hcl
resource "aws_key_pair" "operator" {
  key_name   = "review-master-operator"
  public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIW/0mYPrfhjhpDQNJUt2NqWu4hi3MXUfSpf7zcy7anj renjithraj2005@gmail.com"
}
```

And remove `key_name` from the `aws_instance.app` resource:
```hcl
  key_name               = aws_key_pair.operator.key_name  # remove this line
```

- [x] **Step 3: Remove operator_ip variable**

In `deployment/terraform/variables.tf`, remove:
```hcl
variable "operator_ip" {
  description = "Your public IP in CIDR notation for SSH access, e.g. 59.94.147.0/32"
  type        = string
}
```

- [x] **Step 4: Remove operator_ip from terraform.tfvars**

In `deployment/terraform/terraform.tfvars`, remove:
```hcl
operator_ip    = "117.254.10.46/32"
```

- [x] **Step 5: Validate**

```bash
terraform validate
```
Expected: `Success! The configuration is valid.`

- [x] **Step 6: Commit**

```bash
git add deployment/terraform/security_groups.tf \
        deployment/terraform/ec2.tf \
        deployment/terraform/variables.tf \
        deployment/terraform/terraform.tfvars
git commit -m "feat(terraform): remove SSH access - port 22, key pair, operator_ip variable"
```

---

### Task 5: First Terraform apply — create new resources

This apply creates the Secrets Manager secret, Route 53 record, attaches the managed policy, and removes SSH. It does NOT delete SSM yet.

- [x] **Step 1: Plan and review**

Run from `deployment/terraform/`:
```bash
terraform plan -var-file=terraform.tfvars
```

Expected additions:
- `aws_secretsmanager_secret.app` — new
- `aws_secretsmanager_secret_version.app` — new
- `aws_route53_record.app` — new
- `aws_iam_role_policy_attachment.ec2_ssm` — new

Expected changes:
- `aws_iam_role_policy.ec2` — updated (SSM/KMS removed, Secrets Manager added)
- `aws_iam_role_policy.github_actions` — updated (SSM removed, Secrets Manager added)
- `aws_security_group.ec2` — SSH rule removed
- `aws_instance.app` — key_name removed

Expected destructions:
- `aws_key_pair.operator` — deleted

Review the plan carefully before applying.

- [x] **Step 2: Apply**

```bash
terraform apply -var-file=terraform.tfvars
```

Type `yes` when prompted.

Expected: `Apply complete!` with no errors.

---

### Task 6: Copy real values into Secrets Manager

Now populate the real production values in the Secrets Manager secret. The secret currently has placeholder values from Terraform.

- [x] **Step 1: Open Secrets Manager in AWS Console**

Go to: **AWS Console → Secrets Manager → review-master/prod → Retrieve secret value → Edit**

- [x] **Step 2: Copy each real value from SSM Parameter Store**

Open a second tab: **AWS Console → Systems Manager → Parameter Store → filter by `/review-master/prod`**

For each SSM parameter, copy the real value into the Secrets Manager JSON. The keys are identical. Pay special attention to:
- `DJANGO_SECRET_KEY` — the actual secret key
- `DATABASE_URL` — the actual RDS endpoint and password
- `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`
- `FERNET_SALT_KEY`
- `OPENAI_API_KEY`
- `LANGSMITH_API_KEY`
- `RESEND_API_KEY`
- `SENTRY_DSN`

Also update these four domain values to the new subdomain:
- `CADDY_DOMAIN` → `app.reviewbee.in`
- `DJANGO_ALLOWED_HOSTS` → `app.reviewbee.in`
- `SITE_URL` → `https://app.reviewbee.in`
- `GOOGLE_OAUTH_REDIRECT_URI` → `https://app.reviewbee.in/oauth/google/callback/`

- [x] **Step 3: Save the secret**

Click **Save** in the console. The secret now has all real values.

---

### Task 7: Rewrite `load-secrets.sh` to use Secrets Manager

**Files:**
- Modify: `deployment/scripts/load-secrets.sh`

- [x] **Step 1: Replace the file content**

```bash
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
```

- [x] **Step 2: Commit**

```bash
git add deployment/scripts/load-secrets.sh
git commit -m "feat(scripts): rewrite load-secrets.sh to use Secrets Manager"
```

---

### Task 8: Update deploy.yml smoke test

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [x] **Step 1: Replace the smoke test domain lookup**

Find the `Smoke test` step in `.github/workflows/deploy.yml` and replace the `DOMAIN` lookup:

Change:
```yaml
      - name: Smoke test
        env:
          AWS_REGION: ${{ env.AWS_REGION }}
        run: |
          DOMAIN=$(aws ssm get-parameter \
            --name "/review-master/prod/CADDY_DOMAIN" \
            --with-decryption \
            --query "Parameter.Value" \
            --output text)
          echo "Smoke testing https://$DOMAIN/healthz/"
          curl -fsSL "https://$DOMAIN/healthz/" | grep -q "ok" && echo "Healthcheck passed."
```

To:
```yaml
      - name: Smoke test
        env:
          AWS_REGION: ${{ env.AWS_REGION }}
        run: |
          DOMAIN=$(aws secretsmanager get-secret-value \
            --secret-id "review-master/prod" \
            --region "$AWS_REGION" \
            --query "SecretString" \
            --output text \
            | python3 -c "import json,sys; print(json.load(sys.stdin)['CADDY_DOMAIN'])")
          echo "Smoke testing https://$DOMAIN/healthz/"
          curl -fsSL "https://$DOMAIN/healthz/" | grep -q "ok" && echo "Healthcheck passed."
```

- [x] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat(ci): update smoke test to read domain from Secrets Manager"
```

---

### Task 9: Verify on EC2 via Session Manager

Before deleting SSM, verify the new setup works end-to-end using Session Manager (first time without SSH).

- [x] **Step 1: Install Session Manager plugin on your Mac (one-time)**

```bash
brew install --cask session-manager-plugin
```

Verify:
```bash
session-manager-plugin --version
```
Expected: version string printed.

- [x] **Step 2: Upload updated scripts to EC2**

From your Mac (not inside the session):
```bash
scp -i ~/.ssh/review-master.pem \
  deployment/scripts/load-secrets.sh \
  deployment/scripts/deploy.sh \
  ec2-user@13.203.163.202:/tmp/
```

Then via Session Manager session (step 3 below):
```bash
sudo cp /tmp/load-secrets.sh /opt/review-master/scripts/load-secrets.sh
sudo cp /tmp/deploy.sh /opt/review-master/scripts/deploy.sh
sudo chmod +x /opt/review-master/scripts/*.sh
```

> **Note:** After SSH is removed (Task 4 Terraform apply), use SSM Run Command to copy files, or commit the scripts and have deploy.sh pull them from S3. For this one-time migration, do the SCP while SSH still works, before applying Terraform.

- [x] **Step 3: Connect to EC2 via Session Manager**

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1
```

Expected: interactive shell on the instance as `ssm-user`.

- [x] **Step 4: Run load-secrets.sh**

```bash
sudo /opt/review-master/scripts/load-secrets.sh
```

Expected output:
```
[load-secrets] Fetching secret review-master/prod...
[load-secrets] Written /etc/review-master.env (29 vars)
```

If you see an error, the IAM policy hasn't propagated yet — wait 30 seconds and retry.

- [x] **Step 4: Run deploy.sh**

```bash
sudo /opt/review-master/scripts/deploy.sh
```

Expected: all 6 containers restart and show healthy. The final line should be `Web healthy after Xs`.

- [x] **Step 5: Verify app.reviewbee.in is live**

```bash
curl -I https://app.reviewbee.in/healthz/
```

Expected: `HTTP/2 200`

- [x] **Step 6: Exit the Session Manager session**

```bash
exit
```

---

### Task 10: Delete SSM parameters (second Terraform apply)

Only do this after Task 9 confirms the app is working on `app.reviewbee.in` with Secrets Manager.

- [x] **Step 1: Delete ssm.tf**

```bash
rm deployment/terraform/ssm.tf
```

- [x] **Step 2: Plan — confirm only SSM resources are destroyed**

```bash
terraform plan -var-file=terraform.tfvars
```

Expected: only `aws_ssm_parameter.app["*"]` resources shown as destroyed (29 of them). Nothing else.

If anything other than SSM parameters is shown for destruction, stop and investigate before applying.

- [x] **Step 3: Apply**

```bash
terraform apply -var-file=terraform.tfvars
```

Type `yes`. Expected: `Apply complete!` — 29 destroyed.

- [x] **Step 4: Commit deletion of ssm.tf**

```bash
git add deployment/terraform/ssm.tf  # stages the deletion
git commit -m "feat(terraform): delete SSM parameters — migrated to Secrets Manager"
```

---

### Task 11: Push to main and verify CI/CD pipeline

- [x] **Step 1: Check current branch and push**

```bash
git log main..HEAD --oneline
git push origin HEAD
```

- [x] **Step 2: Open a PR to main on GitHub**

Title: `feat(infra): app.reviewbee.in + Secrets Manager + Session Manager`

- [x] **Step 3: Merge PR and watch Actions tab**

After merge:
1. CI workflow runs (lint, mypy, tests)
2. Deploy workflow triggers after CI passes
3. Smoke test should hit `https://app.reviewbee.in/healthz/` and return `Healthcheck passed.`

- [x] **Step 4: Final verification**

```bash
curl -I https://app.reviewbee.in/healthz/
```

Expected: `HTTP/2 200`

Visit `https://app.reviewbee.in/` in your browser — login page should load with full styles.
