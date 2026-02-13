# LAN Public Access Plan (2026-02-12)
Status: Draft  
Owner: Platform/Website  
Scope: Expose LAN-hosted website to external users without moving app runtime off LAN.

## Goal
Make the existing website reachable from the internet while:
1. Keeping the app running on the current LAN machine.
2. Avoiding inbound port-forwarding on the router.
3. Adding access control in front of the app.

## Constraints
1. Current stack should remain mostly unchanged.
2. Environment is currently unmanaged from a cybersecurity governance perspective.
3. Rollout must be reversible in minutes.

## Decision
Use Cloudflare Tunnel + Cloudflare Access in front of the existing FastAPI website.

### Chosen traffic path
1. User browser -> Cloudflare edge (TLS).
2. Cloudflare edge -> `cloudflared` tunnel (outbound-only from LAN host).
3. `cloudflared` -> local origin (`http://127.0.0.1:8000` by default for this repo).

### Why this path
1. No public inbound firewall/port-forwarding required.
2. Origin IP can stay non-public.
3. Access policies can block anonymous internet traffic before it reaches app code.

## Workstreams

### WS1: Baseline and hardening prep
Tasks:
1. Confirm website runs locally on the host (`website` service).
2. Prefer loopback bind for origin (`127.0.0.1`) instead of `0.0.0.0` when tunnel-only.
3. Ensure env values support public hostname:
   - `DISCORD_REDIRECT_URI=https://<public-host>/auth/callback`
   - `CORS_ORIGINS` includes the public host.
4. Decide public hostname (example: `stats.example.com`).

Done criteria:
1. Local health checks pass on loopback.
2. OAuth callback URL and CORS are aligned with final hostname.

### WS2: Tunnel pilot (non-production)
Tasks:
1. Install `cloudflared` on LAN host.
2. Run one pilot using temporary URL:
   - `cloudflared tunnel --url http://127.0.0.1:8000`
3. Validate external reachability and basic app flows.

Done criteria:
1. External test user can load home page through pilot URL.
2. No service regressions on LAN.

### WS3: Production hostname + Access policy
Tasks:
1. Create named tunnel.
2. Configure tunnel ingress for final hostname.
3. Route DNS through Cloudflare tunnel route.
4. Add Cloudflare Access app policy (email/IdP allowlist).
5. Run `cloudflared` as persistent systemd service.

Done criteria:
1. `https://<public-host>` resolves and serves website.
2. Unauthenticated users are blocked by Access.
3. Tunnel auto-starts after host reboot.

### WS4: Operational readiness
Tasks:
1. Document restart procedures for website and tunnel.
2. Add monitoring checks:
   - tunnel service health
   - origin health (`/api/status`)
3. Add incident playbook for:
   - tunnel down
   - Access misconfiguration
   - origin app down

Done criteria:
1. Operators can recover service using only runbook steps.
2. Basic weekly checks are defined.

## Risk Register
| Risk | Impact | Mitigation |
|---|---|---|
| Host still bound on `0.0.0.0` | LAN exposure wider than needed | Bind origin to `127.0.0.1` when possible |
| Public hostname added without Access | Unintended public access | Enforce Access policy before sharing URL |
| OAuth callback mismatch | Login failures | Update `DISCORD_REDIRECT_URI` to public hostname |
| Cloudflared service not persistent | Outage after reboot | Install and verify systemd unit |
| Config drift across docs/services | Slow incident response | Keep one canonical runbook and checklist |

## Rollback Plan
1. Disable public DNS route for hostname (or delete Access app + tunnel route).
2. Stop/disable `cloudflared` service on LAN host.
3. Keep website serving LAN-only traffic.

Expected rollback time: 5 to 15 minutes.

## Acceptance Criteria
1. External authorized users can access website reliably over HTTPS.
2. Unauthorized users are blocked at Cloudflare Access.
3. LAN app remains unchanged except minimal env/service configuration.
4. Recovery procedure is documented and tested once.

## Deliverables
1. `docs/LAN_PUBLIC_ACCESS_PLAN_2026-02-12.md` (this file).
2. `docs/LAN_PUBLIC_ACCESS_CLOUDFLARE_TUNNEL_RUNBOOK.md` (operator how-to).
