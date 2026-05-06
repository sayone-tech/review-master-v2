# Environment Variables & Secrets

All production secrets live in a single **AWS Secrets Manager** secret: `review-master/prod` (region `ap-south-1`). On every deploy, `load-secrets.sh` pulls the secret and writes `/etc/review-master.env` on the EC2 — all containers read from that file.

## Viewing the Current Secret

AWS Console → Secrets Manager → `review-master/prod` → **Retrieve secret value**.

Or via CLI:

```bash
aws secretsmanager get-secret-value \
  --secret-id review-master/prod \
  --region ap-south-1 \
  --query SecretString \
  --output text | python3 -m json.tool
```

## Changing a Secret Value

1. Go to **AWS Console → Secrets Manager → `review-master/prod`**
2. Click **Retrieve secret value** → **Edit**
3. Change the value(s)
4. Click **Save**
5. **The change is NOT live yet** — the running containers still use the old `/etc/review-master.env`

### Apply the change to the running app

Connect to the EC2 and reload:

```bash
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# On the EC2:
sudo /opt/review-master/scripts/load-secrets.sh      # re-writes /etc/review-master.env
sudo docker compose -f /opt/review-master/docker-compose.prod.yml up -d   # restarts containers with new env
```

### Which services need a restart?

| Change | Restart needed? |
|--------|----------------|
| `DJANGO_SECRET_KEY` | Yes — all app containers (`web`, `worker`, `beat`) |
| `DATABASE_URL` | Yes — all app containers |
| `OPENAI_API_KEY` | Yes — `worker` |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET` | Yes — `web` |
| `CADDY_DOMAIN` | Yes — `caddy` |
| `REDIS_URL` | Yes — all app containers |
| `SENTRY_DSN` | Yes — all app containers |
| `OPENAI_MODEL` | Yes — `worker` |

To restart a single service instead of everything:

```bash
sudo docker compose -f /opt/review-master/docker-compose.prod.yml restart web
sudo docker compose -f /opt/review-master/docker-compose.prod.yml restart worker
```

## Secret Variables Reference

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django cryptographic key — do not rotate unless compromised (invalidates sessions) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts — must include `app.reviewbee.in,127.0.0.1,localhost` |
| `SITE_URL` | Full public URL used in emails and OAuth redirects |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string (`redis://redis:6379` — internal Docker network) |
| `GOOGLE_OAUTH_CLIENT_ID` | Google Cloud OAuth 2.0 client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud OAuth 2.0 client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | Must match what's registered in Google Cloud Console |
| `FERNET_SALT_KEY` | Key for encrypting Google refresh tokens — do not rotate (breaks existing tokens) |
| `OPENAI_API_KEY` | OpenAI API key for review enrichment |
| `OPENAI_MODEL` | Model to use (`gpt-4o-mini-2024-07-18`) |
| `LANGSMITH_API_KEY` | LangSmith tracing key (optional) |
| `SENTRY_DSN` | Sentry error tracking DSN |
| `RESEND_API_KEY` | Transactional email API key |
| `DEFAULT_FROM_EMAIL` | Sender address for all outbound email |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket for static files |
| `CADDY_DOMAIN` | Domain Caddy serves and obtains TLS cert for |
| `CADDY_ACME_EMAIL` | Email for Let's Encrypt notifications |

## What Happens on Each Deploy

`deploy.sh` always calls `load-secrets.sh` before restarting containers, so a normal code deploy automatically picks up any secret changes made since the last deploy. You only need to manually reload if you want a secret change applied **without** a code deploy.
