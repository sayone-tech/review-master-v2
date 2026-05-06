# Database

**RDS PostgreSQL 16** — `db.t4g.micro`, single-AZ, 20 GB gp3 (auto-scales to 100 GB).

| Item | Value |
|------|-------|
| Identifier | `review-master-prod` |
| Endpoint | `review-master-prod.cr6oa6eq8krh.ap-south-1.rds.amazonaws.com:5432` |
| Database name | `reviewmaster` |
| Username | `reviewbee` |
| Region | `ap-south-1` |

The RDS instance is in a **private subnet** — it cannot be reached from the internet. Access is only possible from the EC2 instance (via its security group).

## Connect to the Database

Connect via the EC2 using Session Manager, then use the `web` container's `dbshell`:

```bash
# 1. Start Session Manager
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# 2. On the EC2 — open Django dbshell (uses DATABASE_URL from /etc/review-master.env)
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py dbshell
```

Or connect with `psql` directly:

```bash
# Get the password from Secrets Manager first
DB_PASS=$(aws secretsmanager get-secret-value \
  --secret-id review-master/prod \
  --region ap-south-1 \
  --query SecretString \
  --output text | python3 -c "import json,sys; print(json.load(sys.stdin)['DATABASE_URL'])" \
  | sed 's/.*:\(.*\)@.*/\1/')

sudo docker run --rm -it \
  --network review-master_default \
  postgres:16 \
  psql "postgresql://reviewbee:${DB_PASS}@review-master-prod.cr6oa6eq8krh.ap-south-1.rds.amazonaws.com:5432/reviewmaster"
```

## Backups

Automated backups are enabled with **7-day retention**, taken daily between 03:00–04:00 UTC (08:30–09:30 IST). Point-in-time recovery is available within the retention window.

```bash
# List available snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier review-master-prod \
  --region ap-south-1 \
  --query "DBSnapshots[*].{ID:DBSnapshotIdentifier,Time:SnapshotCreateTime,Status:Status}" \
  --output table
```

## Running Migrations

Migrations run automatically on every deploy (step 4 in `deploy.sh`). To run them manually:

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py migrate --noinput
```

## Checking Database Size

```bash
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py dbshell

-- In psql:
SELECT pg_size_pretty(pg_database_size('reviewmaster'));
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
  FROM pg_tables WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
  LIMIT 10;
```

## Deletion Protection

The RDS instance has **deletion protection enabled** — it cannot be deleted from the AWS console or CLI without first disabling it in Terraform (`deletion_protection = false`) and applying. This is intentional.
