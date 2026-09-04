# Production Compose

Files:

- `docker-compose.prod.yml` — five services: caddy, web (Daphne), worker, beat, redis. No Postgres — uses RDS. (Flower is dev/staging-only and not run in prod — CLAUDE.md §12.7/§22.)
- `.env.example` — template; the populated copy on the box lives at `/etc/review-master/app.env` (mode `0640`, `root:docker`) and is generated from SSM by `../scripts/fetch-ssm-env.sh` (TBD).
- `../caddy/Caddyfile` — reverse proxy, Let's Encrypt auto-TLS, security headers.

## Notes

- **No `build:` section.** The image is built by GitHub Actions and pulled from ECR. `docker compose up` should never compile anything on the production box.
- **Image tag** is pinned via `IMAGE_TAG`. CI updates this and triggers a redeploy. `latest` is convenient for first deploy but switch to immutable git-sha tags for production.
- **Logs** ship to CloudWatch via the `awslogs` driver. The EC2 instance profile needs `logs:CreateLogStream` + `logs:PutLogEvents` on `/review-master/prod`.
- **Migrations** run as a one-off step in the deploy workflow before bringing services up:
  ```
  docker compose run --rm web python manage.py migrate
  ```
- **Static files** are uploaded to S3 in CI (`collectstatic --no-input` writing to S3 via `django-storages`). They are NOT served from the box.
- **Flower** is NOT run in production (dev/staging only — CLAUDE.md §12.7/§22). For task visibility on the box use `docker compose ... exec worker celery -A config inspect active` (see docs/sre/monitoring.md).
- **Redis** persists to a Docker volume (`redis_data`) with AOF on. Capped at 256 MB with `allkeys-lru` eviction so it can't OOM the box. Celery broker / result backend share the same Redis instance using different DB indexes (handled in Django settings).

## First-deploy commands on the EC2 box

```bash
# After SSM env is materialised at /etc/review-master/app.env:
cd /opt/review-master
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker compose --env-file /etc/review-master/app.env -f docker-compose.prod.yml pull
docker compose --env-file /etc/review-master/app.env -f docker-compose.prod.yml \
  run --rm web python manage.py migrate
docker compose --env-file /etc/review-master/app.env -f docker-compose.prod.yml up -d
```
