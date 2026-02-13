# LAN Public Access Runbook: Cloudflare Tunnel
Status: Draft  
Date: 2026-02-12  
Applies to: `website` service in this repository

## Purpose
Expose the LAN-hosted website externally with minimal application changes.

## Current repo defaults
1. Website default origin: `http://127.0.0.1:8000` (from `WEBSITE_PORT`, default `8000`).
2. FastAPI app entrypoint: `website.backend.main:app`.
3. Existing service file currently binds `0.0.0.0` in `website/etlegacy-website.service`.

Recommended for tunnel-only exposure:
1. Bind website to `127.0.0.1` to reduce local network surface.

## Prerequisites
1. A Cloudflare-managed domain.
2. Cloudflare Zero Trust enabled for your account.
3. Shell access on LAN host that runs website.
4. Website healthy locally before tunnel work starts.

## Step 1: Verify local origin
```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/status
```
Expected: HTTP `200`.

If not healthy, fix app/service first before continuing.

## Step 2: Align website env for public hostname
Choose hostname (example: `stats.example.com`), then update `website/.env`:

```env
DISCORD_REDIRECT_URI=https://stats.example.com/auth/callback
CORS_ORIGINS=https://stats.example.com,http://localhost:8000,http://127.0.0.1:8000
WEBSITE_HOST=127.0.0.1
WEBSITE_PORT=8000
```

Restart website service after env changes.

## Step 3: Install cloudflared
Use the install method from Cloudflare docs for your OS.

Linux quick check after install:
```bash
cloudflared --version
```

## Step 4: Authenticate and create named tunnel
```bash
cloudflared tunnel login
cloudflared tunnel create slomix-website
```

Capture the generated Tunnel UUID from output.

## Step 5: Create tunnel config
Create `/etc/cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /etc/cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: stats.example.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Copy tunnel credentials JSON into `/etc/cloudflared/` and set secure perms:

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/<TUNNEL_UUID>.json /etc/cloudflared/
sudo chown root:root /etc/cloudflared/<TUNNEL_UUID>.json
sudo chmod 600 /etc/cloudflared/<TUNNEL_UUID>.json
```

## Step 6: Route DNS hostname to tunnel
```bash
cloudflared tunnel route dns slomix-website stats.example.com
```

## Step 7: Run tunnel as service
Install/start service using Cloudflare-recommended service setup for your OS.
Then verify:

```bash
sudo systemctl enable cloudflared
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager
```

## Step 8: Add Cloudflare Access policy (required)
In Cloudflare Zero Trust dashboard:
1. Access -> Applications -> Add application.
2. Type: Self-hosted.
3. Domain: `stats.example.com`.
4. Policy:
   - Action: Allow
   - Include: specific emails, email domain, or IdP group
5. Optional second policy:
   - Action: Block
   - Include: Everyone

Do not distribute the URL until this policy is active.

## Step 9: Validation checklist
1. Public DNS resolves:
```bash
dig +short stats.example.com
```
2. Access protection works:
   - unauthenticated browser should be redirected/challenged by Access.
3. Authenticated user can open site and load API calls.
4. OAuth login callback succeeds.
5. Local origin remains private:
   - no router port forwarding exists for website port.

## Step 10: Operations
Common commands:
```bash
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared -n 100 --no-pager

sudo systemctl restart etlegacy-website
sudo systemctl status etlegacy-website --no-pager
sudo tail -n 100 logs/website.log
```

## Troubleshooting
1. `502 Bad Gateway` on public host:
   - website origin down or wrong port in tunnel config.
2. Access loop or blocked users:
   - policy scope mismatch or wrong identity include rules.
3. Discord OAuth fails after going public:
   - `DISCORD_REDIRECT_URI` still points to old LAN/localhost URL.
4. Tunnel up but wrong app:
   - wrong hostname mapping in ingress or DNS route.

## Rollback
1. Remove/disable public DNS tunnel route.
2. Stop tunnel service:
```bash
sudo systemctl stop cloudflared
sudo systemctl disable cloudflared
```
3. Keep website LAN-only.

## Optional pilot mode (no custom domain)
For a fast external smoke test only:
```bash
cloudflared tunnel --url http://127.0.0.1:8000
```
This creates a temporary `trycloudflare.com` URL and is not intended as long-term production.
