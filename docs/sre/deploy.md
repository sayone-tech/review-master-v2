# Deploy & Rollback

## Normal Deploy (automatic)

Merging to `main` triggers the GitHub Actions pipeline:

1. **CI** (`.github/workflows/ci.yml`) — runs lint, type-check, tests
2. **Deploy** (`.github/workflows/deploy.yml`) — runs only if CI passes:
   - Builds Docker image (linux/arm64 for Graviton)
   - Pushes to ECR with `:latest` and `:<git-sha>` tags
   - Sends SSM Run Command to EC2 → runs `/opt/review-master/scripts/deploy.sh`
   - `deploy.sh` pulls secrets, pulls image, runs migrations, collects static, restarts containers
   - Smoke tests `https://app.reviewbee.in/healthz/`

Monitor progress in the **Actions** tab on GitHub.

## Manual Deploy (ad-hoc)

Useful to redeploy the current image without a code change (e.g. after updating a secret):

```bash
aws ssm send-command \
  --region ap-south-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=tag:Project,Values=review-master" \
  --parameters 'commands=["/opt/review-master/scripts/deploy.sh"]' \
  --output text \
  --query "Command.CommandId"
```

Or connect via Session Manager and run directly:

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# On the EC2:
sudo /opt/review-master/scripts/deploy.sh
```

## Rollback to a Previous Image

Every deploy pushes a `:<git-sha>` tag to ECR alongside `:latest`. To roll back:

1. Find the SHA you want to roll back to:

   ```bash
   # List recent ECR images with push dates
   aws ecr describe-images \
     --repository-name review-master/app \
     --region ap-south-1 \
     --query 'sort_by(imageDetails, &imagePushedAt)[-10:].{Tag:imageTags[0],Pushed:imagePushedAt}' \
     --output table
   ```

2. Connect to the EC2 and redeploy with that specific tag:

   ```bash
   aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

   # On the EC2:
   ECR_IMAGE="270587882826.dkr.ecr.ap-south-1.amazonaws.com/review-master/app:<sha>"
   sudo -E docker compose -f /opt/review-master/docker-compose.prod.yml pull
   sudo -E docker compose -f /opt/review-master/docker-compose.prod.yml up -d
   ```

   Replace `<sha>` with the commit SHA from step 1.

## Check Deploy Status

```bash
# After standard session setup:
docker compose -f /opt/review-master/docker-compose.prod.yml ps

# Check which image is currently running
docker inspect review-master-web-1 | grep Image

# Check app is responding
curl -fsSL https://app.reviewbee.in/healthz/
```

## Run Django Management Commands

`docker compose run` requires `ECR_IMAGE` to be set. Always switch to root and export it first:

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# On the EC2 — switch to root and set ECR_IMAGE
sudo -i
ECR_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export ECR_IMAGE="${ECR_ACCOUNT}.dkr.ecr.ap-south-1.amazonaws.com/review-master/app:latest"

# Now run any management command
docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py <command>

# Examples:
docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py shell

docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py createsuperuser
```

## Create a Superuser

Superusers are created once manually — there is no seed data for them.

```bash
# 1. Connect to the EC2
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# 2. On the EC2 — run createsuperuser inside the web container
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py createsuperuser
```

You will be prompted for:

- **Username** — use an email address (matches the custom User model)
- **Email** — same as username
- **Password** — minimum 10 characters (enforced by Django validators)

The superuser can then log in at `https://app.reviewbee.in/admin/` and at the main app with the Superadmin role.

> **Note:** Never share superuser credentials. Create one account per person who needs superadmin access.

## Update Deployment Scripts

The deploy scripts (`deploy.sh`, `load-secrets.sh`, `docker-compose.prod.yml`, `Caddyfile`) live in the repo under `deployment/`. Changes to these files are **not** automatically synced to the EC2 — they must be copied manually or via a bootstrap mechanism.

To push updated scripts:

```bash
# Upload to S3 (the EC2 user-data script pulls from here on first boot)
aws s3 cp deployment/scripts/deploy.sh s3://review-master-static-prod/deploy/deploy.sh
aws s3 cp deployment/scripts/load-secrets.sh s3://review-master-static-prod/deploy/load-secrets.sh
aws s3 cp deployment/compose/docker-compose.prod.yml s3://review-master-static-prod/deploy/docker-compose.prod.yml

# Then sync to the live EC2 via SSM
aws ssm send-command \
  --region ap-south-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=tag:Project,Values=review-master" \
  --parameters 'commands=["aws s3 cp s3://review-master-static-prod/deploy/deploy.sh /opt/review-master/scripts/deploy.sh && chmod +x /opt/review-master/scripts/deploy.sh"]' \
  --output text
```
