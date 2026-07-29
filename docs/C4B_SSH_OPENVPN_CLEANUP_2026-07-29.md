# SSH/openvpn cleanup proposal — 2026-07-29

Part of a maintenance/cleanup sweep (task C4b in a session working-doc,
`docs/TASKS_FOR_SONNET_2026-07-29.md` — not tracked in this repo, so that filename is not a
citable source; the findings below are independently reproducible from this host directly).
Both items below are **outside the git repo** (home-directory / system state) and involve
key material or an installed package, so this document is a recommendation only —
no deletion is performed by this PR, and none should happen without the owner's explicit
go-ahead in the moment, run as the `samba` user specifically (see the note on `~`
expansion below).

## 1. `~/.ssh/autorized_keys` (typo, missing the "h")

**Measured:**
```
-rw-rw-r-- 1 samba samba 404 Dec 30  2023 /home/samba/.ssh/autorized_keys
```
- `sshd` only reads `authorized_keys` and `authorized_keys2` by default — this filename is
  never consulted, **provided the host doesn't override `AuthorizedKeysFile`.** Checked the
  effective config on this host, not just the compiled-in default:
  ```
  $ grep -n AuthorizedKeysFile /etc/ssh/sshd_config
  40:#AuthorizedKeysFile	.ssh/authorized_keys .ssh/authorized_keys2
  $ grep -n '^Include\|^Match' /etc/ssh/sshd_config
  12:Include /etc/ssh/sshd_config.d/*.conf
  $ grep -rl 'AuthorizedKeysFile\|Match' /etc/ssh/sshd_config.d/
  (no output — none of the three drop-ins override it or add a Match block)
  ```
  `AuthorizedKeysFile` is commented out (= compiled-in default in effect) and no drop-in or
  `Match` block overrides it — confirmed dead on this host, not just "dead by default."
- This file holds **public** keys — an authorized-keys list is an access-control file, not
  private key material — but `0664` (group-writable, world-readable) is still too open for
  something that controls SSH access to this account: a group member or any local user could
  read it, and a group member could append their own key.
- Real `~/.ssh/authorized_keys` (`0600`, last modified today) is the one actually in effect
  and is untouched by this proposal.

**Recommendation:** delete `~/.ssh/autorized_keys`. It is dead weight with unnecessarily
open permissions, and unlike the two old RSA keys the owner asked to keep in the real
`authorized_keys` file ("a script probably uses them"), this file is not referenced from
anywhere sshd or any script reads.

**Owner-gated — not run by this PR. Must run as the `samba` user** — `~` expands to
whichever account runs the command, and this measurement is specific to `/home/samba`; a
root shell (plausible here, since the package cleanup below needs one) would leave the
measured file untouched and could delete an unrelated file under a different account's home:
```bash
rm -- /home/samba/.ssh/autorized_keys
```

## 2. `openvpn` package

**Correction against the original task note:** the backlog claimed openvpn was "installed
with no configuration at all." That is not accurate — `/etc/openvpn/` holds a full set of
ProtonVPN `.ovpn` configs (root-owned, dated 2024-03-30) for ~60 countries, plus a
`client/` directory. So there **is** configuration; it's just unused right now:

```bash
$ systemctl is-enabled openvpn
disabled
$ systemctl list-units --all | grep openvpn || true
# (no output — no loaded unit)
```

`systemctl`'s unit checks only prove no *systemd-managed* OpenVPN session exists — a
manually-launched process or a NetworkManager VPN connection wouldn't show up there. Checked
both directly:
```
$ pgrep -x openvpn; echo "exit:$?"
exit:1                                    # no such process running
$ command -v nmcli; echo "exit:$?"
exit:1                                    # NetworkManager's CLI isn't even installed
$ systemctl is-active NetworkManager
inactive
```
NetworkManager isn't installed/running on this host at all (a server typically uses
`systemd-networkd`/netplan directly, not NetworkManager), so there's no NetworkManager-VPN
path to check further — confirmed no OpenVPN session by any mechanism, not just "no systemd
unit."

Tailscale (`tailscaled`, active) is what's actually used for the project's own connectivity
needs. But the ProtonVPN configs look like a personal VPN setup unrelated to the slomix
project, not project infrastructure — removing them is a bigger call than "delete dead
config" and is the owner's to make, not something to infer from "it isn't currently running."

**Recommendation:** leave `openvpn` and `/etc/openvpn/` alone unless the owner confirms
these ProtonVPN configs are no longer wanted. If confirmed, `apt purge openvpn` removes the
package; the `/etc/openvpn/` config directory would need a separate explicit `rm -rf` since
purge doesn't always clear third-party-managed config trees.

## Verify (after owner executes either step)

Same `~`-expansion caveat as the deletion command above — verify with the
absolute path, not `~`, so this actually checks `/home/samba/.ssh` and not
whatever account's home the verifying shell happens to be:
```bash
ls /home/samba/.ssh/    # autorized_keys (typo) gone, authorized_keys + the two old RSA keys untouched
dpkg -l | grep openvpn  # only if the owner confirmed removal
```
