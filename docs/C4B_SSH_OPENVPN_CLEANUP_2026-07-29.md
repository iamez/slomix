# SSH/openvpn cleanup proposal — 2026-07-29

Part of the maintenance/cleanup sweep from `docs/TASKS_FOR_SONNET_2026-07-29.md` (task C4b).
Both items below are **outside the git repo** (home-directory / system state) and involve
sensitive material or an installed package, so this document is a recommendation only —
no deletion is performed by this PR, and none should happen without the owner's explicit
go-ahead in the moment.

## 1. `~/.ssh/autorized_keys` (typo, missing the "h")

**Measured:**
```
-rw-rw-r-- 1 samba samba 404 Dec 30  2023 /home/samba/.ssh/autorized_keys
```
- `sshd` only reads `authorized_keys` and `authorized_keys2` by default — this filename is
  never consulted. It is confirmed dead from sshd's perspective.
- `0664` (group+other readable, group writable) is too open for a file holding key material,
  regardless of whether it's read.
- Real `~/.ssh/authorized_keys` (`0600`, last modified today) is the one actually in effect
  and is untouched by this proposal.

**Recommendation:** delete `~/.ssh/autorized_keys`. It is dead weight with unnecessarily
open permissions, and unlike the two old RSA keys the owner asked to keep in the real
`authorized_keys` file ("a script probably uses them"), this file is not referenced from
anywhere sshd or any script reads.

**Owner-gated — not run by this PR:**
```bash
rm ~/.ssh/autorized_keys
```

## 2. `openvpn` package

**Correction against the original task note:** the backlog claimed openvpn was "installed
with no configuration at all." That is not accurate — `/etc/openvpn/` holds a full set of
ProtonVPN `.ovpn` configs (root-owned, dated 2024-03-30) for ~60 countries, plus a
`client/` directory. So there **is** configuration; it's just unused right now:

```
systemctl is-enabled openvpn   → disabled
systemctl list-units --all | grep openvpn   → no loaded unit
```

Tailscale (`tailscaled`, active) is what's actually used for the project's own connectivity
needs. But the ProtonVPN configs look like a personal VPN setup unrelated to the slomix
project, not project infrastructure — removing them is a bigger call than "delete dead
config" and is the owner's to make, not something to infer from "it isn't currently running."

**Recommendation:** leave `openvpn` and `/etc/openvpn/` alone unless the owner confirms
these ProtonVPN configs are no longer wanted. If confirmed, `apt purge openvpn` removes the
package; the `/etc/openvpn/` config directory would need a separate explicit `rm -rf` since
purge doesn't always clear third-party-managed config trees.

## Verify (after owner executes either step)
```bash
ls ~/.ssh/            # autorized_keys (typo) gone, authorized_keys + the two old RSA keys untouched
dpkg -l | grep openvpn  # only if the owner confirmed removal
```
