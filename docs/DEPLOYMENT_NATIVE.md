# Deploying ClaraMed natively on an Oracle Cloud free VM (no Docker)

Runbook for one Ubuntu VM on Oracle Cloud's "Always Free" tier. Everything runs as normal system services:
PostgreSQL and Redis from Ubuntu's packages, ClaraMed's API, worker and scheduler as `systemd` services, and
Caddy for automatic HTTPS. For the Docker version see `docs/DEPLOYMENT_VM.md`.

> **Status: written and statically tested, but the steps below have not been run on an Ubuntu VM.** The author had
> no Ubuntu machine. What was verified instead: the app's production startup guard, the post-deploy checker over
> real HTTP, a prefork Celery worker plus scheduler passing the live smoke test (on macOS), and the unit files,
> env template and scripts against `tests/unit/test_native_deploy_files.py`. Expect to fix small things on the
> first run, and work through section 8 before pointing JeevaCare at it.

> **Free is fine for a pilot, not for production patient data.** Oracle gives no uptime promise or support on the
> free tier, can run out of capacity, and may reclaim idle free instances. When real patient data is involved,
> move to a small paid VM; these same steps apply unchanged.

## 1. What you get

```
internet -> Caddy :80/:443 (HTTPS) -> API 127.0.0.1:8000 -> PostgreSQL, Redis (loopback only)
                                       worker, scheduler  -> PostgreSQL, Redis, /var/lib/claramed/storage
```

| Piece | Where |
|-------|-------|
| Code | `/opt/claramed/app` (git clone) |
| Python 3.11 + packages | `/opt/claramed/venv` |
| Settings and secrets | `/etc/claramed/claramed.env` (mode 640, owner root, group claramed) |
| Files and state | `/var/lib/claramed` |
| Services | `claramed-migrate`, `claramed-api`, `claramed-worker`, `claramed-beat` (run as the `claramed` user) |
| Logs | `journalctl -u <service>` |

## 2. Create the Oracle VM

1. Sign up at https://www.oracle.com/cloud/free/. A card is needed for identity verification. Choose an India
   **home region** (Mumbai or Hyderabad): it cannot be changed later, and free-tier capacity differs per region.
2. Console menu, Compute, Instances, **Create instance**:
   - Image: **Canonical Ubuntu 24.04** (the aarch64/ARM build).
   - Shape: Change shape, Ampere, **VM.Standard.A1.Flex**, **2 OCPU and 12 GB** memory. (The free allowance is
     4 OCPU and 24 GB in total across A1 instances; 2 and 12 is plenty and leaves room.)
   - Networking: keep the default VCN and subnet, and assign a public IPv4 address.
   - Add SSH keys: paste your **public** key (`cat ~/.ssh/id_ed25519.pub` on your Mac; create one with
     `ssh-keygen -t ed25519` if you have none).
   - Boot volume: 100 GB (the free allowance is 200 GB in total).
3. "Out of capacity" is common for the free ARM shape. Retry later, try another availability domain, or use a
   smaller shape (1 OCPU and 6 GB still runs ClaraMed).
4. Once running, note the public IP. Then Networking, Reserved Public IPs, and attach a reserved IP so the address
   survives stop and start.
5. Open the cloud firewall: Networking, Virtual Cloud Networks, your VCN, your subnet, its **Security List**,
   Add Ingress Rules: source `0.0.0.0/0`, protocol TCP, destination port `80`; add a second rule for `443`.
6. **Recommended:** upgrade the account to **pay-as-you-go** (Billing) while staying inside the free limits. As far
   as Oracle documents, idle reclamation applies to Always Free accounts; check their current terms. You are
   only charged if you exceed the free resources, so do not add paid resources.
7. Point DNS at it: create an **A record** for your domain (for example `claramed.yourdomain.com`) with the VM's
   public IP.

## 3. Prepare the OS

```bash
ssh ubuntu@<public-ip>
sudo apt update && sudo apt -y upgrade
sudo timedatectl set-timezone UTC
```

Oracle's Ubuntu images also block ports at the VM's own firewall (`iptables`), separately from the Security List.
Open 80 and 443 there and make it permanent:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
sudo iptables -L INPUT -n --line-numbers
```

In that listing both new `ACCEPT` rules must appear **before** the `REJECT` rule. Do not enable `ufw` on top of this.

## 4. Install the software

```bash
sudo apt install -y postgresql redis-server tesseract-ocr tesseract-ocr-eng poppler-utils \
    libgl1 libglib2.0-0 git curl ca-certificates debian-keyring debian-archive-keyring apt-transport-https gpg

# Caddy, from its official repository (https://caddyserver.com/docs/install#debian-ubuntu-raspbian)
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Python 3.11 (the version ClaraMed was built and tested on; Ubuntu 24.04 ships 3.12). Use `uv`, installed as root,
with Python placed in a shared directory the service user can read. Read the installer first if you wish
(https://docs.astral.sh/uv/getting-started/installation/):

```bash
sudo -i
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
export UV_PYTHON_INSTALL_DIR=/opt/uv-python
uv python install 3.11
exit
```

## 5. Create the service user, code and environment

```bash
sudo useradd --system --create-home --home-dir /var/lib/claramed --shell /usr/sbin/nologin claramed
sudo install -d -o claramed -g claramed -m 750 /var/lib/claramed/storage /opt/claramed

# code (use the branch or tag you intend to run; for a private repo set up a deploy key first)
sudo -u claramed git clone --branch feat/jeevacare-integration https://github.com/KunalMK25/claramed.git /opt/claramed/app

# virtualenv with pip included, then CPU-only PyTorch (the default wheel is a multi-GB GPU build), then the rest
sudo -i
UV_PYTHON_INSTALL_DIR=/opt/uv-python /root/.local/bin/uv venv --seed --python 3.11 /opt/claramed/venv
chown -R claramed:claramed /opt/claramed
exit
sudo -u claramed /opt/claramed/venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
sudo -u claramed /opt/claramed/venv/bin/python -m pip install -r /opt/claramed/app/requirements.txt

# download the X-ray model weights once, so the first job does not have to
sudo -u claramed HOME=/var/lib/claramed /opt/claramed/venv/bin/python -c \
    "import torchxrayvision as xrv; xrv.models.DenseNet(weights='densenet121-res224-all')"
```

The pip steps take 10 to 20 minutes on a small VM.

**Database and queue**

```bash
openssl rand -hex 24          # this is the database password; copy it, you need it twice below
sudo -u postgres psql -c "CREATE ROLE claramed LOGIN PASSWORD '<paste-the-password>'"
sudo -u postgres createdb -O claramed claramed
sudo sed -i 's/^appendonly no/appendonly yes/' /etc/redis/redis.conf && sudo systemctl restart redis-server
```

PostgreSQL and Redis listen on the loopback interface only by default on Ubuntu; leave it that way.

**Settings**

```bash
sudo install -d -m 755 /etc/claramed
sudo cp /opt/claramed/app/deploy/native/claramed.env.example /etc/claramed/claramed.env
sudo chown root:claramed /etc/claramed/claramed.env
sudo chmod 640 /etc/claramed/claramed.env
sudo nano /etc/claramed/claramed.env
```

Replace every `CHANGE_ME`: the database password inside `DATABASE_URL` (the one from above), `API_KEY_HASH_SECRET` and
`SECRET_KEY` (each from `openssl rand -hex 32`), and `GROQ_API_KEY`. The app refuses to start in production with
defaults, short secrets or `DEBUG` on. Changing `API_KEY_HASH_SECRET` later invalidates every issued API key.

## 6. Start everything

```bash
sudo cp /opt/claramed/app/deploy/native/claramed-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now claramed-migrate claramed-api claramed-worker claramed-beat

sudo install -m 755 /opt/claramed/app/deploy/native/claramed-run.sh /usr/local/bin/claramed-run

sudo cp /opt/claramed/app/deploy/native/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/claramed.example.com/<your-domain>/' /etc/caddy/Caddyfile
sudo systemctl restart caddy

systemctl --no-pager status claramed-migrate claramed-api claramed-worker claramed-beat caddy
curl -s http://127.0.0.1:8000/api/v1/health
```

If a service is not `active`: `journalctl -u claramed-api -n 100 --no-pager` (swap the name). The first Caddy start
needs DNS to point at the VM; it then fetches the certificate by itself.

`claramed-run` runs any command as the service user with the production settings loaded. Register JeevaCare
(prints the API key and webhook secret **once**; store them in your password manager):

```bash
sudo claramed-run python scripts/register_client.py --name jeevacare \
    --webhook-url https://<jeevacare-backend>/api/webhook/claramed-callback \
    --allowed-host res.cloudinary.com
```

## 7. Backups

```bash
sudo crontab -e
# add:  17 2 * * * /opt/claramed/app/scripts/backup_native.sh >> /var/log/claramed-backup.log 2>&1
sudo /opt/claramed/app/scripts/backup_native.sh        # run once now and check it prints "backup ok"
```

`scripts/backup_native.sh` writes compressed dumps to `/var/backups/claramed`, rejects an empty dump and keeps
14 days. A backup on the same disk does not survive losing the disk: copy the folder off the VM regularly, for
example to your own machine (`scp ubuntu@<ip>:/var/backups/claramed/* .` needs read access, so run it as root via
`sudo`) or to Oracle Object Storage (a free allowance exists). Files in `/var/lib/claramed/storage` only hold jobs
in flight, so the database is what to back up.

**Restore** (replaces the current data):

```bash
sudo systemctl stop claramed-api claramed-worker claramed-beat
gunzip -c claramed-<stamp>.sql.gz | sudo -u postgres psql -d claramed
sudo systemctl start claramed-api claramed-worker claramed-beat
```

Rehearse a restore once on a spare machine before you need it.

## 8. Verify (do not skip)

From your own machine:

```bash
CLARAMED_API_KEY=sk_claramed_... python scripts/post_deploy_check.py --base-url https://<your-domain>
```

All 9 checks must pass. Then on the VM, run the live end-to-end check. It briefly creates and then deletes a
throwaway client and test rows, and must print `PASS`:

```bash
sudo claramed-run python scripts/jeevacare_smoke.py
```

Also check in a browser that `https://<your-domain>/api/v1/health/ready` shows `"status": "ready"`, that the
certificate is valid, and that `http://` redirects to `https://`.

## 9. Operating

| Task | Command |
|------|---------|
| Status | `systemctl --no-pager status claramed-api claramed-worker claramed-beat caddy` |
| Logs | `journalctl -u claramed-worker -f` (also `claramed-api`, `claramed-beat`, `caddy`) |
| Restart | `sudo systemctl restart claramed-worker` |
| Update | `sudo /opt/claramed/app/scripts/update_native.sh` (pulls, installs, migrates, restarts), then `post_deploy_check.py` |
| Rollback | `sudo -u claramed git -C /opt/claramed/app checkout <previous commit>`, then run `update_native.sh` again. Migrations are additive; restore a backup if one must be undone. |
| Pause the integration | set `CLARAMED_INTEGRATION_ENABLED=false` in `/etc/claramed/claramed.env`, then `sudo systemctl restart claramed-api` (callers get 503) |
| Disable a client | `sudo -u postgres psql -d claramed -c "UPDATE integration_clients SET active=false WHERE client_name='jeevacare'"` |
| Memory and disk | `free -h`, `df -h`, `systemctl status claramed-worker` |

Monitoring is not built in. Point an uptime monitor at `https://<domain>/api/v1/health/ready` and alert on failure and
on certificate expiry. What runs on its own: callback retries (5 attempts over about 30 minutes), the hourly purge of
results older than `RESULT_RETENTION_DAYS`, the 10-minute sweeper for stuck jobs, service restarts after crashes
and reboots, and Ubuntu's automatic security updates.

## 10. Troubleshooting

| Symptom | Likely cause and fix |
|---------|----------------------|
| Site unreachable on port 80/443 | Check both firewalls: the Security List (section 2, step 5) and `iptables` (section 3). Test from outside: `curl -I http://<ip>`. |
| Caddy cannot get a certificate | DNS does not yet point at the VM, or ports 80/443 are blocked. `journalctl -u caddy -n 50`. |
| `claramed-api` fails with "Refusing to start" | A secret in the env file is a default, too short, or `DEBUG` is on. Fix and restart. |
| `claramed-migrate` fails | Wrong database password in `DATABASE_URL`, or the `claramed` role/database was not created (section 5). |
| `claramed-worker` keeps restarting | Out of memory (`dmesg \| grep -i kill`), or a missing package. Read `journalctl -u claramed-worker`. |
| `exec format error` or a wheel is missing during pip | Wrong CPU architecture or Python version; confirm `uname -m` and that the venv is Python 3.11. |
| Jobs stay `queued` | Worker or Redis is down. After `STALE_JOB_SECONDS` they fail and the client is called back. |
| `deliveryStatus` is `failed` | JeevaCare's callback route rejects the call (signature, token, or it crashes on `results: null`). Results remain available from `/status`. |
| 422 `host_not_allowed` for a legitimate file | The file host is not in the client's `--allowed-host` list. |

## 11. Known limits

- **One VM is a single point of failure.** If it dies, ClaraMed is down until you restore onto a new VM from backup.
- The Oracle free tier has no uptime promise, may be out of capacity, and may reclaim idle instances.
- No metrics, tracing or alerting stack is included; logs live in the system journal.
- Webhook secrets and callback tokens are stored in the database in plaintext (tracked in `TODOS.md`).
- The steps in this runbook have not been run on Ubuntu; see the status note at the top.
- Security hardening beyond this (patching policy, intrusion detection, a formal review) is out of scope; see
  `docs/SECURITY.md` for the application-level model.

## 12. Pre-launch checklist

- [ ] DNS points at the VM; certificate issued; `http` redirects to `https`
- [ ] Both firewalls allow 22, 80, 443 and nothing else is exposed; SSH is key-only
- [ ] `/etc/claramed/claramed.env` is mode 640, not in git, secrets random and kept in a password manager
- [ ] `scripts/post_deploy_check.py` passes 9/9 with a real API key
- [ ] `scripts/jeevacare_smoke.py` prints PASS on the VM
- [ ] Backup cron installed, one dump exists, copied off the VM, restore rehearsed once
- [ ] Uptime monitor on `/api/v1/health/ready` with alerts
- [ ] Account upgraded to pay-as-you-go (or you accept the idle-reclamation risk)
- [ ] JeevaCare's owner has confirmed their callback route accepts the signature and bearer token
- [ ] Decision recorded on sending patient text to Groq; secrets-encryption TODO accepted or done
