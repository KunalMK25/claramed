# Deploying ClaraMed on one VM (Docker Compose)

Production runbook for a single Linux VM. Everything runs in containers: Caddy (HTTPS), the API, the Celery
worker, the Celery scheduler, Redis and PostgreSQL. For local development use `docker-compose.yml` and
`docs/DEPLOYMENT.md` instead.

> **Status: written and statically tested, but the Docker build and the compose stack have not been run
> end to end.** The author had no Docker available. The first deploy is therefore also the first real build:
> do it on a staging VM (or the real one, before pointing JeevaCare at it) and work through section 7.
> Everything else that could be checked without Docker was: the app's production startup guard, the
> post-deploy checker over real HTTP, and the compose/Dockerfile properties in `tests/unit/test_deploy_files.py`.

## 1. What you get

```
internet -> Caddy :80/:443 (automatic HTTPS) -> api :8000 -> postgres, redis
                                                worker, beat -> postgres, redis, shared storage volume
```

Only Caddy listens on the public interface. Postgres, Redis and the API are not published. Data lives in named
Docker volumes (`pgdata`, `redisdata`, `storage`, `caddy_data`). API and worker share the `storage` volume,
which is what makes local file storage safe here.

## 2. Sizing

| Resource | Minimum | Comfortable |
|----------|---------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB (each worker process holds the X-ray model, about 1 GB) |
| Disk | 30 GB | 60 GB (image is several GB; Postgres, uploads and backups grow) |
| OS | Ubuntu 22.04 / 24.04, x86_64 or ARM64 | |

X-ray inference runs on the CPU and takes seconds per image. Raise `WORKER_CONCURRENCY` only together with RAM.

## 3. Before you start

- A domain whose A/AAAA record points at the VM's public IP (Caddy needs it to get a certificate).
- Ports 80 and 443 reachable from the internet.
- A Groq API key (`GROQ_API_KEY`) for document explanations.
- The ClaraMed code on the VM (`git clone` of your repository, or `rsync`). The branch must be pushed first.
- The open launch items in `TODOS.md` decided (in particular: sending extracted patient text to Groq).

## 4. Prepare the VM

Install Docker Engine and the Compose plugin by following the official instructions for your OS
(https://docs.docker.com/engine/install/), then:

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
sudo ufw enable
sudo timedatectl set-timezone UTC
```

## 5. Configure

```bash
cd /opt/claramed                       # wherever you put the code
cp .env.production.example .env
chmod 600 .env
```

Edit `.env`. Generate each secret with `openssl rand -hex 32`:

- `CLARAMED_DOMAIN`: your domain.
- `POSTGRES_PASSWORD`: a hex string (it goes into a URL, so avoid `@ : /`).
- `API_KEY_HASH_SECRET`, `SECRET_KEY`: random, 32 or more characters. **The app refuses to start in
  production with the defaults, with `DEBUG` on, or with short secrets.**
- `GROQ_API_KEY`.

Changing `API_KEY_HASH_SECRET` later invalidates every issued API key. Treat it as permanent.

## 6. Start

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f migrate api worker caddy
```

The first build downloads PyTorch (CPU) and the X-ray model and takes 10 to 20 minutes. `migrate` runs once and
exits with code 0; `api`, `worker`, `beat` and `caddy` then start. `ps` should show `api` and `worker` as
`healthy`.

Register JeevaCare (prints the API key and webhook secret once; store them in your password manager):

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/register_client.py \
    --name jeevacare \
    --webhook-url https://<jeevacare-backend>/api/webhook/claramed-callback \
    --allowed-host res.cloudinary.com
```

Optional Streamlit UI (reachable only on the VM; use `ssh -L 8501:localhost:8501 user@vm`): register a second
client for it, put its key in `.env` as `CLARAMED_UI_API_KEY`, then add `--profile ui` to the `up` command.

## 7. Verify (do not skip)

From your own machine:

```bash
CLARAMED_API_KEY=sk_claramed_... python scripts/post_deploy_check.py --base-url https://<your-domain>
```

All 9 checks must pass: health, readiness, anonymous access refused, docs not exposed, HSTS header, key accepted,
file-host allowlist enforced, job scoping. Then run one real analysis through the stack:

1. Open `https://<your-domain>/api/v1/health/ready` in a browser: `"status": "ready"`.
2. `docker compose -f docker-compose.prod.yml exec worker python scripts/jeevacare_smoke.py`: the smoke test,
   with the real worker. Run it in the **worker** container: it starts a callback receiver on `127.0.0.1`, which
   only the worker's own container can reach. It must print `PASS`.
3. Confirm the certificate is valid and `http://<domain>` redirects to `https://`.

## 8. Backups

```bash
chmod +x scripts/backup.sh
crontab -e     # add:  17 2 * * * cd /opt/claramed && ./scripts/backup.sh >> backups/backup.log 2>&1
```

`scripts/backup.sh` writes a compressed dump to `backups/`, rejects an empty dump, and keeps 14 days. **A backup
on the same disk does not survive losing the disk**: copy `backups/` somewhere else (object storage or another
machine). The `storage` volume only holds files for jobs in flight (source files are deleted after analysis), so
the database is the thing to back up.

**Restore** (this replaces the current data):

```bash
docker compose -f docker-compose.prod.yml stop api worker beat
gunzip -c backups/claramed-<stamp>.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U claramed -d claramed
docker compose -f docker-compose.prod.yml up -d
```

Rehearse a restore once on a spare VM before you need it.

## 9. Operating

| Task | Command |
|------|---------|
| Status | `docker compose -f docker-compose.prod.yml ps` |
| Logs | `docker compose -f docker-compose.prod.yml logs -f --tail=200 api worker beat` |
| Restart one service | `docker compose -f docker-compose.prod.yml restart worker` |
| Update | `git pull && docker compose -f docker-compose.prod.yml up -d --build`, then run `post_deploy_check.py` |
| Rollback | `git checkout <previous commit> && docker compose -f docker-compose.prod.yml up -d --build` (schema migrations are additive; restore a backup if a migration itself must be undone) |
| Pause the integration | set `CLARAMED_INTEGRATION_ENABLED=false` in `.env`, then `up -d api` (callers get 503) |
| Disable a client | `docker compose -f docker-compose.prod.yml exec postgres psql -U claramed -d claramed -c "UPDATE integration_clients SET active=false WHERE client_name='jeevacare'"` |
| Disk use | `docker system df` and `df -h` |

Monitoring is not built in. At minimum point an uptime monitor at `https://<domain>/api/v1/health/ready` and alert
on failures and on certificate expiry; watch free disk and memory on the VM.

What runs on its own: the worker retries failed callbacks (5 attempts over about 30 minutes), the scheduler purges
results older than `RESULT_RETENTION_DAYS` hourly and fails jobs stuck longer than `STALE_JOB_SECONDS`.
Containers restart after a reboot (`restart: unless-stopped`).

## 10. Troubleshooting

| Symptom | Likely cause and fix |
|---------|----------------------|
| `api` restarts, log says "Refusing to start with an unsafe production configuration" | A secret in `.env` is missing, default or too short. Fix and `up -d`. |
| Caddy cannot get a certificate | DNS does not point at the VM yet, or ports 80/443 are blocked. `docker compose ... logs caddy`. |
| `worker` shows `unhealthy` or restarts | Out of memory: raise VM RAM or lower `WORKER_CONCURRENCY`; check `docker stats`. |
| Jobs stay `queued` | Worker or Redis is down: `ps`, then `logs worker redis`. After `STALE_JOB_SECONDS` they fail and the client is called back. |
| `deliveryStatus` is `failed` | JeevaCare's callback route rejects the call (signature, token, or it crashes on `results: null`). Results are still available from `/status`. |
| `migrate` exits non-zero | Read `logs migrate`; usually the database password in `.env` does not match an existing `pgdata` volume. |
| 422 `host_not_allowed` for a legitimate file | The file host is not in the client's `--allowed-host` list. |

## 11. Known limits

- **One VM is a single point of failure.** If it dies, ClaraMed is down until you restore it. Recovery is
  restore-from-backup onto a new VM (plan for an hour or more), not automatic failover.
- No metrics, tracing or alerting stack is included; logs are local JSON files capped at 50 MB per service.
- Webhook secrets and callback tokens are stored in the database in plaintext (tracked in `TODOS.md`).
- The compose stack and image build are untested; see the status note at the top.
- Security hardening beyond this (WAF, intrusion detection, patching policy, a formal review) is out of scope;
  see `docs/SECURITY.md` for the application-level model.

## 12. Pre-launch checklist

- [ ] DNS points at the VM; certificate issued; `http` redirects to `https`
- [ ] `.env` is mode 600, not in git, secrets are random and stored in a password manager
- [ ] `scripts/post_deploy_check.py` passes 9/9 with a real API key
- [ ] `scripts/jeevacare_smoke.py` prints PASS inside the worker container
- [ ] Backup cron installed, a dump exists, copied off the VM, restore rehearsed once
- [ ] Uptime monitor on `/api/v1/health/ready` with alerts
- [ ] JeevaCare's owner has confirmed their callback route accepts the signature and bearer token
- [ ] Decision recorded on sending patient text to Groq; secrets-encryption TODO accepted or done
- [ ] VM firewall allows only 22, 80, 443; SSH is key-only
