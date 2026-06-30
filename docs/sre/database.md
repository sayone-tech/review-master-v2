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

> **Note:** the `web` image does **not** ship the `psql` client, so `manage.py dbshell`
> fails with `You appear not to have the 'psql' program installed`. To run SQL you have
> two options: a throwaway `postgres:16` container (below), or — for one-off statements —
> run them through Django's own connection (no psql needed):
>
> ```bash
> docker compose -f /opt/review-master/docker-compose.prod.yml \
>   run --rm web python manage.py shell -c "
> from django.db import connection
> with connection.cursor() as c:
>     c.execute('SELECT version();')
>     print(c.fetchone())
> "
> ```

Run the [standard session setup](README.md) first. To get an interactive `psql` prompt,
use a throwaway `postgres:16` container:

```bash
# Get the password from Secrets Manager first
DB_PASS=$(aws secretsmanager get-secret-value \
  --secret-id review-master/prod \
  --region ap-south-1 \
  --query SecretString \
  --output text | python3 -c "import json,sys; print(json.load(sys.stdin)['DATABASE_URL'])" \
  | sed 's/.*:\(.*\)@.*/\1/')

docker run --rm -it \
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

Migrations run automatically on every deploy (step 4 in `deploy.sh`). To run them manually (after [standard session setup](README.md)):

```bash
docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py migrate --noinput
```

## Checking Database Size

The `web` image has no `psql`, so run the query through Django's connection:

```bash
docker compose -f /opt/review-master/docker-compose.prod.yml \
  run --rm web python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute('''
        SELECT pg_size_pretty(pg_database_size('reviewmaster'));
    ''')
    print(c.fetchone())
    c.execute('''
        SELECT schemaname, tablename,
               pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
        FROM pg_tables WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        LIMIT 10;
    ''')
    for row in c.fetchall():
        print(row)
"
```

## Deletion Protection

The RDS instance has **deletion protection enabled** — it cannot be deleted from the AWS console or CLI without first disabling it in Terraform (`deletion_protection = false`) and applying. This is intentional.
