# Server Access

There is **no SSH**. Access is via AWS Systems Manager Session Manager — no key pairs, no open ports.

## Prerequisites (one-time setup)

1. **AWS CLI** with the `review-master` profile configured:
   ```bash
   aws configure --profile review-master
   # Use account 270587882826, region ap-south-1
   ```
   Or ensure `AWS_PROFILE=review-master` is in your shell profile.

2. **Session Manager plugin** for the AWS CLI:
   ```bash
   # macOS (Apple Silicon)
   curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/mac_arm64/sessionmanager-bundle.zip" \
     -o /tmp/sessionmanager-bundle.zip
   unzip -o /tmp/sessionmanager-bundle.zip -d /tmp
   sudo /tmp/sessionmanager-bundle/install

   # macOS (Intel)
   curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/mac/sessionmanager-bundle.zip" \
     -o /tmp/sessionmanager-bundle.zip
   unzip -o /tmp/sessionmanager-bundle.zip -d /tmp
   sudo /tmp/sessionmanager-bundle/install

   # Verify
   session-manager-plugin --version
   ```

## Start a Session

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1
```

You land as `ssm-user`. Always switch to root and export `ECR_IMAGE` before running any Docker Compose command (see [README — Standard EC2 Session Setup](README.md)):

```bash
sudo -i
export ECR_IMAGE="270587882826.dkr.ecr.ap-south-1.amazonaws.com/review-master/app:latest"
```

## End a Session

Type `exit` (twice if you switched to root) or press `Ctrl+D`.

## Check What's Running

```bash
# After sudo -i and export ECR_IMAGE
docker compose -f /opt/review-master/docker-compose.prod.yml ps
```

Expected output — all services should show `healthy` or `running`:

```
NAME                        STATUS
review-master-caddy-1       running
review-master-web-1         healthy
review-master-worker-1      healthy
review-master-beat-1        running
review-master-flower-1      running
review-master-redis-1       healthy
```

## Access Flower (Celery Task Monitor)

Flower runs on `127.0.0.1:5555` inside the EC2 — not exposed publicly. Use SSM port forwarding:

```bash
aws ssm start-session \
  --target i-0782bee2ff9885151 \
  --region ap-south-1 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["5555"],"localPortNumber":["5555"]}'
```

Then open `http://localhost:5555` in your browser.
