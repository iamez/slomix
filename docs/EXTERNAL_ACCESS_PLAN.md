# External Access Plan — Cloudflare Tunnel + Zero Trust

> **Status**: Plan ready for implementation | **Date**: 2026-02-15
> **Goal**: Make the Slomix website reachable by external testers without opening any inbound ports.

---

## Table of Contents

- [Scenario Summary](#scenario-summary)
- [Options Matrix](#a-options-matrix)
- [Recommended Approach](#b-recommended-approach-cloudflare-tunnel--zero-trust-access)
- [Implementation Plan](#c-step-by-step-implementation-plan)
- [Tester Experience (UX)](#tester-experience-ux-flow)
- [Guardrails](#d-guardrails)
- [Threat Model](#threat-model-summary)
- [Architecture Diagram](#architecture-diagram)
- [Cost Summary](#cost-summary)
- [Implementation Priority](#implementation-priority)
- [Sources](#sources)

---

## Scenario Summary

| Item | Value |
|------|-------|
| **Service** | FastAPI SPA on Uvicorn |
| **Origin** | `localhost:8000` (HTTP, no TLS at origin) |
| **Other LAN services** | PostgreSQL `:5432`, Discord bot, SSH — must NOT be exposed |
| **Inbound ports** | ALL CLOSED (no port forwarding, no public IP) |
| **Goal** | External testers reach the website; LAN stays sealed |
| **Cookie note** | `https_only=True` session cookies — works correctly because Cloudflare terminates TLS at the edge; the browser sees `https://` |

---

## A) Options Matrix

| Criterion | **Cloudflare Tunnel + Access** | **Tailscale Funnel** | **VPS Reverse Proxy + WireGuard** | **ngrok** |
|---|---|---|---|---|
| **Setup effort** | Low-Medium (~1 hr) | Low | High | Low |
| **Tester friction** | Email OTP (4-6 clicks first time, 0 after) | None (public) OR client install | None (public URL) | None (public URL) |
| **Security** | Excellent — Zero Trust gate, WAF, DDoS, ingress-locked | Good — WireGuard E2E, but no WAF/DDoS | Good — full control, but you maintain everything | Poor — interstitial warning, 2h sessions, random URLs |
| **LAN isolation** | Excellent — outbound-only, explicit single-service ingress | Good — only declared services | Good — VPS is sole entry point | Fair — agent on LAN with broader potential |
| **DDoS protection** | Yes (100+ Tbps CF edge) | No | Only if you add it yourself | No |
| **Custom domain** | Yes (your domain via CNAME) | No (`.ts.net` subdomain only) | Yes | Paid plans only ($8+/mo) |
| **Cost** | **Free** (up to 50 Zero Trust users, unlimited tunnel bandwidth) | Free (personal, 10 Mbps limit) | $5-20/mo VPS + maintenance time | Free tier very limited |
| **Operational burden** | Low — managed edge, auto-reconnect | Low | High — patch VPS, WireGuard, certs, DDoS | Low but unstable |
| **Privacy** | Medium — CF can inspect traffic | High — E2E encrypted | High — self-hosted | Medium — ngrok sees traffic |
| **Production readiness** | Mature, enterprise-grade | Beta | Production-ready if maintained | Not suitable for production |
| **Rollback** | `systemctl stop cloudflared` = instant | Stop funnel = instant | Tear down VPS | Stop ngrok = instant |

---

## B) Recommended Approach: Cloudflare Tunnel + Zero Trust Access

**Why this wins for our scenario:**

1. **No inbound ports needed** — `cloudflared` makes outbound-only connections. LAN firewall stays completely untouched.
2. **Surgical exposure** — Ingress rules explicitly map ONE hostname to ONE service (`localhost:8000`). PostgreSQL, Discord bot, SSH — all invisible. Catch-all returns 404.
3. **Gated access** — Zero Trust Access with email OTP means only allowlisted emails can reach the site. No IdP required. Testers enter email, get code, done.
4. **Temporary auth** — For ad-hoc testers: tester requests access, admin gets an approval email, grants for up to 24 hours.
5. **Free** — Tunnel is free. Access is free for up to 50 users. WAF free tier gives 5 custom rules + rate limiting.
6. **HTTPS solved** — Cloudflare terminates TLS at the edge. `https_only=True` cookies work correctly since the browser sees HTTPS.
7. **Instant rollback** — `systemctl stop cloudflared` and the site vanishes from the internet in seconds.

---

## C) Step-by-Step Implementation Plan

### Phase 1: DNS & Cloudflare Account (15 min)

```
1. Sign up / log in at https://dash.cloudflare.com
2. Add your domain (e.g., slomix.com) to Cloudflare
3. Update your domain registrar's nameservers to Cloudflare's NS records
4. Wait for DNS propagation (usually < 30 min)
```

> If you already use Cloudflare for DNS, skip to Phase 2.

### Phase 2: Install cloudflared (5 min)

On the LAN server (the machine running FastAPI):

```bash
# Debian/Ubuntu
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Authenticate (opens browser to Cloudflare login)
cloudflared tunnel login
# Creates ~/.cloudflared/cert.pem
```

### Phase 3: Create the Tunnel (5 min)

```bash
cloudflared tunnel create slomix-website
# Outputs: Tunnel UUID and creates ~/.cloudflared/<TUNNEL-UUID>.json
```

Note the `<TUNNEL-UUID>` for the config below.

### Phase 4: Configuration File

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL-UUID>
credentials-file: /home/<user>/.cloudflared/<TUNNEL-UUID>.json

ingress:
  # ONLY the website — nothing else
  - hostname: test.slomix.com
    service: http://localhost:8000
    originRequest:
      connectTimeout: 10s
      noTLSVerify: false

  # Catch-all: reject everything else (CRITICAL for safety)
  - service: http_status:404
```

Validate before deploying:

```bash
cloudflared tunnel ingress validate
# Should pass with no errors

cloudflared tunnel ingress rule https://test.slomix.com
# Should show: Using service http://localhost:8000

cloudflared tunnel ingress rule https://evil.com
# Should show: Using service http_status:404
```

### Phase 5: DNS Route

```bash
cloudflared tunnel route dns slomix-website test.slomix.com
# Creates CNAME: test.slomix.com -> <TUNNEL-UUID>.cfargotunnel.com
```

In Cloudflare dashboard, set SSL/TLS mode to **Full** (not Flexible, not Full Strict — since origin is HTTP).

### Phase 6: Run as systemd Service

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
sudo systemctl status cloudflared

# Quick test
curl -I https://test.slomix.com
```

### Phase 7: Zero Trust Access — Gate the Site (10 min)

1. Go to **Cloudflare Zero Trust Dashboard** at `https://one.dash.cloudflare.com`

2. **Enable One-time PIN identity provider:**
   - Settings > Authentication > Identity providers > Add > **One-time PIN**

3. **Create an Access Application:**
   - Access > Applications > Add application > **Self-hosted**
   - Application name: `Slomix Website Test`
   - Application domain: `test.slomix.com`
   - Session duration: `24 hours`

4. **Create an Allow policy:**
   - Policy name: `Approved Testers`
   - Action: **Allow**
   - Include rule: **Emails** — add each tester's email
   - Example: `tester1@gmail.com`, `tester2@outlook.com`

5. **Save** — Site now requires email OTP login.

### Phase 7b: Temporary Auth for Ad-hoc Testers (Optional)

For testers who shouldn't have standing access:

1. Create a **second Allow policy** in the same application:
   - Policy name: `Temporary Testers`
   - Action: **Allow**
   - Include: **Emails** — ad-hoc tester emails
   - Additional settings > Enable **Purpose justification**
   - Enable **Temporary authentication**
   - Approver emails: your admin email
2. **Order**: Persistent policy ABOVE temporary policy

**Flow**: Tester enters email > gets OTP > submits justification > admin gets approval email > approves for up to 24h.

### Phase 8: Update FastAPI CORS

In `website/backend/main.py`, add the tunnel hostname to allowed CORS origins:

```python
origins = [
    "https://test.slomix.com",
    # ... existing origins
]
```

### Phase 9: Verify End-to-End

```bash
# Test the full flow
curl -I https://test.slomix.com
# Should return 302 redirect to Cloudflare Access login

# Verify tunnel health
cloudflared tunnel info slomix-website

# Watch logs
journalctl -u cloudflared -f
```

---

## Tester Experience (UX Flow)

### What the tester sees

```
1. Click invite URL: https://test.slomix.com
       |
2. Cloudflare Access login page appears
   - "Enter your email" -> types their email
   - Clicks "Send me a code"
       |
3. Checks email (arrives in 10-30 sec)
   - "Your code: 123456 (valid for 10 minutes)"
       |
4. Enters code on the page -> Clicks "Verify"
       |
5. Redirected to the Slomix website
   - Session lasts 24 hours (or 7 days, configurable)
       |
6. Subsequent visits within session: ZERO clicks, instant access
```

**Total first-time friction: 4-6 clicks. After that: 0 clicks.**

### Invite Template

```
Subject: Access to Slomix Testing Site

Hi! You've been granted access to test the Slomix website.

URL: https://test.slomix.com

Steps:
1. Visit the URL above
2. Enter your email address
3. Check your inbox for a one-time code
4. Enter the code — you're in!

Access expires: [DATE]. Questions? Reply to this email.
```

### Double-Auth Consideration

The site has Discord OAuth built in. With CF Access added, testers face two logins.

| Approach | Pros | Cons |
|----------|------|------|
| **Keep both** (recommended initially) | Defense-in-depth, no code changes | Two logins on first visit |
| **Detect CF header, skip Discord OAuth** | Single login for testers | Requires FastAPI code change |
| **Bypass CF Access, rely on Discord OAuth only** | Single login | Loses Zero Trust gate + DDoS protection at auth layer |

**Recommendation**: Start with both logins active (no code changes). If tester friction becomes a real complaint, add CF header detection later — `Cf-Access-Authenticated-User-Email` header is injected by Cloudflare and can be trusted when traffic comes through the tunnel.

Optional FastAPI change to skip Discord OAuth for CF-authenticated testers:

```python
async def check_auth(request: Request):
    # Check if user came through Cloudflare Access
    cf_email = request.headers.get("Cf-Access-Authenticated-User-Email")
    if cf_email:
        # Trust CF's authentication — create tester session
        request.state.user = {"email": cf_email, "auth_method": "cloudflare_access", "role": "tester"}
        return True

    # Fall back to Discord OAuth
    discord_session = request.session.get("discord_user")
    if discord_session:
        request.state.user = discord_session
        return True

    raise HTTPException(status_code=401, detail="Authentication required")
```

### Tester Management Quick Reference

| Action | Steps | Time |
|--------|-------|------|
| **Add tester** | CF Dashboard > Access > Policy > add email | ~1 min |
| **Add ad-hoc tester** | Same + enable temp auth, approve via email | ~2 min |
| **Remove tester** | CF Dashboard > Access > Policy > remove email | ~30 sec |
| **Emergency revoke** | Access > Settings > Revoke user sessions | ~30 sec |
| **Let access expire** | Do nothing | Automatic |

---

## D) Guardrails

### Ensuring ONLY the Website is Exposed

| Control | Implementation |
|---------|----------------|
| **Explicit ingress** | Only `test.slomix.com -> http://localhost:8000`. Catch-all returns 404. |
| **No wildcard DNS** | Do NOT use `*.slomix.com`. Only explicit `test.slomix.com`. |
| **No WARP routing** | Do NOT add `warp-routing: enabled: true` — that exposes private network. |
| **Validate config** | `cloudflared tunnel ingress validate` after every change. |
| **Single tunnel** | `cloudflared tunnel list` — ensure only one tunnel exists. |
| **PostgreSQL localhost-only** | Verify `listen_addresses = '127.0.0.1'` in `postgresql.conf`. |
| **Firewall unchanged** | Inbound ports stay CLOSED. Tunnel is outbound-only. |

### Monitoring Checklist

```
[ ] cloudflared running:        sudo systemctl status cloudflared
[ ] Tunnel health:              cloudflared tunnel info slomix-website
[ ] Access audit logs:          CF One Dashboard > Logs > Access
[ ] Website error logs:         tail -f ~/slomix_discord/logs/website_error.log
[ ] Traffic analytics:          CF Dashboard > Analytics > Security
[ ] Active sessions:            CF One Dashboard > Access > Active sessions
[ ] Rate limiting:              CF Dashboard > Security > WAF > Rate limiting rules
```

**Recommended WAF rules (free tier = 5 rules):**

1. Rate limit: 100 req/min per IP on `test.slomix.com`
2. Block known-bad User-Agents
3. Challenge high-risk geolocations (optional)
4. Block requests to sensitive paths (e.g., `/admin` if applicable)
5. Reserved for emergencies

### Rollback Plan

| Scenario | Action | Time |
|----------|--------|------|
| **Emergency: kill all access** | `sudo systemctl stop cloudflared` | 5 seconds |
| **Remove one tester** | CF Dashboard > Access policy > remove email | 1 minute |
| **Disable but keep config** | `sudo systemctl disable --now cloudflared` | 10 seconds |
| **Full teardown** | `cloudflared tunnel delete slomix-website` + remove DNS CNAME | 2 minutes |
| **Uninstall** | `sudo apt remove cloudflared && rm -rf ~/.cloudflared/` | 1 minute |

---

## Threat Model Summary

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| **Origin IP discovered (bypass tunnel)** | Low — no public IP, no A records | High | Never publish origin IP; remove any historical DNS A records; tunnel is outbound-only |
| **Wildcard DNS exposes other services** | Medium if misconfigured | Critical | Use ONLY explicit hostname, NO wildcards |
| **Weak Access policy (any email allowed)** | Medium if careless | High | Explicit email allowlist only — never `*@gmail.com` |
| **cloudflared exposes wrong port** | Low if validated | Critical | Always run `ingress validate`; catch-all = 404; PostgreSQL on localhost only |
| **Session/cookie hijacking** | Low | Medium | CF handles TLS; `https_only=True` + `samesite=lax` cookies are correct |
| **DDoS against tunnel** | Low | Low | Cloudflare's 100+ Tbps edge absorbs volumetric attacks |
| **Tunnel left running after testing** | Medium | Medium | Calendar reminder; `systemctl disable` when testing phase ends |
| **YAML misconfig (indentation)** | Low | Varies | `cloudflared tunnel ingress validate` catches syntax errors; catch-all fails safe |

### Misconfiguration Pitfalls to Avoid

| Pitfall | What Goes Wrong | Prevention |
|---------|-----------------|------------|
| Missing catch-all rule | `cloudflared` fails to start (fail-safe) | Always end ingress with `- service: http_status:404` |
| Wrong rule ordering | First match wins; later rules ignored | Put specific rules first, catch-all last |
| `warp-routing: enabled: true` | Exposes entire private network | Never add this line |
| `noTLSVerify: true` | Disables cert checking to origin | Keep `false` (default); only use `true` with self-signed origin certs |
| Allow any email domain in Access | Anyone with a Gmail account gets in | Use explicit email list, not domain wildcards |
| Stale tunnel after testing | Permanent exposure with no monitoring | Set calendar reminder; `systemctl disable` when done |
| Multiple tunnels on same domain | Traffic split, confusing logs | One tunnel per domain; audit with `cloudflared tunnel list` |

---

## Architecture Diagram

```
+--------------------------------------------------------------+
|  EXTERNAL TESTER                                              |
|    | https://test.slomix.com                                  |
|                                                               |
|  CLOUDFLARE EDGE                                              |
|  +- TLS termination (browser sees HTTPS)                     |
|  +- DDoS protection (100+ Tbps)                              |
|  +- WAF + rate limiting (5 free rules)                       |
|  +- Zero Trust Access gate (email OTP)                       |
|       | (only if authenticated)                               |
|                                                               |
|  CLOUDFLARE TUNNEL (encrypted, outbound-initiated)           |
|       |                                                       |
|                                                               |
|  YOUR LAN SERVER (all inbound ports CLOSED)                  |
|  +- cloudflared daemon -> localhost:8000 only                |
|  |                                                            |
|  +- FastAPI Website :8000    <- EXPOSED (via tunnel)         |
|  +- PostgreSQL :5432         <- NOT exposed (no ingress)     |
|  +- Discord Bot              <- NOT exposed (no ingress)     |
|  +- SSH, other services      <- NOT exposed (catch-all: 404)|
+--------------------------------------------------------------+
```

---

## Cost Summary

| Component | Free Tier | Notes |
|-----------|-----------|-------|
| Cloudflare Tunnel | Unlimited bandwidth | No cap |
| Zero Trust Access | 50 users | More than enough for testing |
| WAF + Rate Limiting | 5 custom rules | Adequate for test site |
| DDoS Protection | Unmetered | Included automatically |
| **Total** | **$0/month** | |

---

## Implementation Priority

| Order | Phase | Time | Priority |
|-------|-------|------|----------|
| 1 | Phases 1-6: Tunnel working, site reachable | ~30 min | Must do |
| 2 | Phase 7: Access gate (email OTP) | ~10 min | **Must do immediately after** — do NOT leave site ungated |
| 3 | Phase 8-9: CORS update + verification | ~10 min | Must do before inviting testers |
| 4 | WAF rules + monitoring setup | ~15 min | Strongly recommended |
| 5 | Phase 7b: Temporary auth for ad-hoc testers | ~10 min | Nice-to-have |
| 6 | CF header detection to skip Discord OAuth | ~30 min code change | Only if double-auth annoys testers |

**Total: ~1 hour for a fully gated, monitored, reversible deployment at zero cost.**

---

## Sources

- [Cloudflare Tunnel documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/)
- [Cloudflare Tunnel config file reference](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/)
- [One-time PIN login](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/)
- [Temporary authentication](https://developers.cloudflare.com/cloudflare-one/policies/access/temporary-auth/)
- [Tunnel firewall best practices](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/deploy-tunnels/tunnel-with-firewall/)
- [Cloudflare WAF rate limiting](https://developers.cloudflare.com/waf/rate-limiting-rules/)
- [Origin IP exposure risks (Medium)](https://p4n7h3rx.medium.com/cloudflare-tunnel-origin-exposure-weaponized-6ae5b1f09bb2)
- [Tailscale Funnel vs Cloudflare Tunnel 2025](https://onidel.com/blog/tailscale-cloudflare-nginx-vps-2025)
- [Cloudflare origin protection analysis](https://www.vaadata.com/blog/cloudflare-how-to-secure-your-origin-server/)
- [Cloudflare Tunnel self-hosting guide](https://itsfoss.com/cloudflare-tunnels/)
