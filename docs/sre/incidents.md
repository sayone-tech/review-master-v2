# Common Incidents

> All `docker compose` commands require the [standard session setup](README.md) — connect via Session Manager, then `sudo -i` and export `ECR_IMAGE`.

## App returning 502 / site is down

**Symptoms:** `https://app.reviewbee.in` returns 502 or times out.

**Diagnosis:**

```bash
# After standard session setup:
docker compose -f /opt/review-master/docker-compose.prod.yml ps

docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=50 web

# Caddy forwards to web — if web is down, Caddy 502s
docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=50 caddy
```

**Fix:** If `web` is stopped/unhealthy, restart it:

```bash
docker compose -f /opt/review-master/docker-compose.prod.yml restart web
```

If the image is corrupted or the container won't start, redeploy:

```bash
/opt/review-master/scripts/deploy.sh
```

---

## Celery tasks not running

**Symptoms:** Reviews not syncing, enrichment not happening, scheduled jobs missed.

**Diagnosis:**

```bash
# After standard session setup:
docker compose -f /opt/review-master/docker-compose.prod.yml \
  exec worker celery -A config inspect ping

docker compose -f /opt/review-master/docker-compose.prod.yml ps beat

docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=100 worker
```

**Fix:**

```bash
docker compose -f /opt/review-master/docker-compose.prod.yml restart worker beat
```

---

## Secret / environment variable wrong

**Symptoms:** App error like `ImproperlyConfigured`, `AuthenticationError`, `OperationalError`.

**Fix:**

1. Update the value in **AWS Console → Secrets Manager → `review-master/prod`**
2. Reload on the EC2 (after standard session setup):
   ```bash
   /opt/review-master/scripts/load-secrets.sh
   /opt/review-master/scripts/deploy.sh
   ```

---

## Database connection errors

**Symptoms:** `django.db.OperationalError`, `could not connect to server`.

**Diagnosis:**

```bash
# Check RDS status (from local machine)
aws rds describe-db-instances \
  --db-instance-identifier review-master-prod \
  --region ap-south-1 \
  --query "DBInstances[0].{Status:DBInstanceStatus,Class:DBInstanceClass}" \
  --output table

# Test connectivity from EC2 (after standard session setup):
docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py dbshell -- -c "SELECT 1;"
```

**Common causes:**
- RDS is in maintenance window (check maintenance window: Mon 04:00–05:00 UTC)
- `DATABASE_URL` in Secrets Manager is wrong — verify the password
- RDS ran out of connections — check `max_connections` (default 87 for `db.t4g.micro`)

---

## TLS certificate not renewing

**Symptoms:** Browser shows certificate expired, Caddy logs show ACME errors.

Caddy handles TLS automatically via Let's Encrypt. Certificates auto-renew before expiry. If renewal fails (after standard session setup):

```bash
docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=100 caddy

# Force Caddy to reload its config
docker compose -f /opt/review-master/docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

**Common causes:**
- DNS not pointing to the right IP (check Route 53 → `app.reviewbee.in` A record = `13.203.163.202`)
- Port 80 blocked (Caddy uses HTTP-01 challenge) — check security group allows port 80

---

## EC2 instance unreachable (no Session Manager)

**Symptoms:** `aws ssm start-session` hangs or errors.

**Diagnosis:** Check if the EC2 is running (from local machine):

```bash
aws ec2 describe-instances \
  --instance-ids i-0782bee2ff9885151 \
  --region ap-south-1 \
  --query "Reservations[0].Instances[0].{State:State.Name,Status:StatusReason}" \
  --output table
```

**Fix options:**
- If stopped: start it from the console
- If the SSM agent is down: reboot the instance from the console (SSM agent starts on boot)
- If the instance is terminated: restore from the latest AMI snapshot or redeploy via Terraform

---

## High CPU / memory

**Check:**

```bash
# From local machine
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=i-0782bee2ff9885151 \
  --start-time $(date -u -v-1H +%FT%TZ) \
  --end-time $(date -u +%FT%TZ) \
  --period 300 \
  --statistics Average \
  --region ap-south-1

# From EC2 (after standard session setup):
docker stats --no-stream
```

**Fix:** If worker is spiking due to many tasks, reduce Celery concurrency in `docker-compose.prod.yml` (`--concurrency=1`) and redeploy.
