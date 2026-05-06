# Common Incidents

## App returning 502 / site is down

**Symptoms:** `https://app.reviewbee.in` returns 502 or times out.

**Diagnosis:**

```bash
# 1. Check all containers
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1
sudo docker compose -f /opt/review-master/docker-compose.prod.yml ps

# 2. Check web logs
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=50 web

# 3. Check Caddy logs (Caddy forwards to web — if web is down, Caddy 502s)
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=50 caddy
```

**Fix:** If `web` is stopped/unhealthy, restart it:

```bash
sudo docker compose -f /opt/review-master/docker-compose.prod.yml restart web
```

If the image is corrupted or the container won't start, redeploy:

```bash
sudo /opt/review-master/scripts/deploy.sh
```

---

## Celery tasks not running

**Symptoms:** Reviews not syncing, enrichment not happening, scheduled jobs missed.

**Diagnosis:**

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# Check worker is alive
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  exec worker celery -A config inspect ping

# Check beat is running
sudo docker compose -f /opt/review-master/docker-compose.prod.yml ps beat

# Check worker logs for errors
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=100 worker
```

**Fix:**

```bash
sudo docker compose -f /opt/review-master/docker-compose.prod.yml restart worker beat
```

---

## Secret / environment variable wrong

**Symptoms:** App error like `ImproperlyConfigured`, `AuthenticationError`, `OperationalError`.

**Fix:**

1. Update the value in **AWS Console → Secrets Manager → `review-master/prod`**
2. Reload on the EC2:
   ```bash
   aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1
   sudo /opt/review-master/scripts/load-secrets.sh
   sudo docker compose -f /opt/review-master/docker-compose.prod.yml up -d
   ```

---

## Database connection errors

**Symptoms:** `django.db.OperationalError`, `could not connect to server`.

**Diagnosis:**

```bash
# Check RDS status
aws rds describe-db-instances \
  --db-instance-identifier review-master-prod \
  --region ap-south-1 \
  --query "DBInstances[0].{Status:DBInstanceStatus,Class:DBInstanceClass}" \
  --output table

# Test connectivity from EC2
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py dbshell -- -c "SELECT 1;"
```

**Common causes:**
- RDS is in maintenance window (check maintenance window: Mon 04:00–05:00 UTC)
- `DATABASE_URL` in Secrets Manager is wrong — verify the password
- RDS ran out of connections — check `max_connections` (default 87 for `db.t4g.micro`)

---

## TLS certificate not renewing

**Symptoms:** Browser shows certificate expired, Caddy logs show ACME errors.

Caddy handles TLS automatically via Let's Encrypt. Certificates auto-renew before expiry. If renewal fails:

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# Check Caddy logs
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=100 caddy

# Force Caddy to reload its config
sudo docker compose -f /opt/review-master/docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

**Common causes:**
- DNS not pointing to the right IP (check Route 53 → `app.reviewbee.in` A record = `13.203.163.202`)
- Port 80 blocked (Caddy uses HTTP-01 challenge) — check security group allows port 80

---

## EC2 instance unreachable (no Session Manager)

**Symptoms:** `aws ssm start-session` hangs or errors.

**Diagnosis:** Check if the EC2 is running:

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
# CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=i-0782bee2ff9885151 \
  --start-time $(date -u -v-1H +%FT%TZ) \
  --end-time $(date -u +%FT%TZ) \
  --period 300 \
  --statistics Average \
  --region ap-south-1

# Check what's using resources on the EC2
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1
sudo docker stats --no-stream
```

**Fix:** If worker is spiking due to many tasks, reduce Celery concurrency in `docker-compose.prod.yml` (`--concurrency=1`) and redeploy.
