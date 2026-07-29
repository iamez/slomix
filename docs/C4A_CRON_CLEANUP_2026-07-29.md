# Cron cleanup — 2026-07-29

Part of a maintenance/cleanup sweep (task C4a in a session working-doc,
`docs/TASKS_FOR_SONNET_2026-07-29.md` — not tracked in this repo, so that filename is not a
citable source; the findings below are independently reproducible from `crontab -l` on this
box). `crontab` is host state, not a repo file, so this document is the deliverable — the
actual edit is an owner-gated `crontab -e` on this box.

## Current state (`crontab -l`, captured 2026-07-29)

```cron
0 3 * * * /usr/local/bin/check-security.sh > /home/samba/share/slomix_discord/logs/cron-security-check.log 2>&1
# Claude auto-run Feb 21 7am - REMOVE AFTER USE
#0 7 21 2 * screen -dmS claude-auto /home/samba/share/slomix_discord/run_claude_auto.sh
# TEST send "please continue" to claude-teams - REMOVE AFTER USE
#4 05 * * * tmux has-session -t claude-lua 2>/dev/null && tmux send-keys -t claude-lua "please continue" && sleep 1 && tmux send-keys -t claude-lua C-m
#5 05 * * * tmux has-session -t claude-run 2>/dev/null && tmux send-keys -t claude-run "please continue" && sleep 1 && tmux send-keys -t claude-run C-m

0 18 28 2 * tmux has-session -t 0 2>/dev/null && tmux send-keys -t 0 "please continue" && sleep 1 && tmux send-keys -t 0 C-m

37 15 25 2 * cd /home/samba/share/slomix_discord && tmux new-session -d -s codex-reset 'codex --enable multi_agent -m gpt-5.3-codex -c model_reasoning_effort="xhigh" -s read-only -a on-request "..."'

15 4 */4 * * /home/samba/backups/backup_etlegacy.sh >> /home/samba/backups/backup.log 2>&1
```

## Classification

| Entry | Keep? | Reason |
|---|---|---|
| `0 3 * * * check-security.sh` | **Keep** | Daily production security check. |
| `15 4 */4 * * backup_etlegacy.sh` | **Keep** | Production backup. **Not** a strict every-4-days interval: cron's `*/4` on the day-of-month field steps through days 1, 5, 9, …, 29 and resets each month, so the actual gap is usually 4 days but drops to as little as 2 at a month boundary (e.g. day 29 → day 1 of the next month). Described accurately here so nobody relies on a strict 4-day guarantee this schedule doesn't provide. |
| 5 already-commented lines (2 `# ... REMOVE AFTER USE` header comments + 3 commented-out cron entries below them) | **Remove** | Already inert (leading `#`), pure clutter. Harmless but should go with the rest of this cleanup. |
| `0 18 28 2 * tmux ... "please continue" ...` | **Remove** | Uncommented one-off from a Feb 2026 Claude session, never marked done. Cron's `day-of-month 28, month February` fires **every year in February**, not just once — left as-is it will silently re-fire in February 2027 against a `tmux` session (`-t 0`) that almost certainly won't exist by then, so it is a no-op today but not intentionally so. |
| `37 15 25 2 * ... codex-reset ...` | **Remove** | Same pattern: uncommented one-off spinning up a `codex` read-only audit session on Feb 25, same yearly-recurrence footgun. Also embeds a long inline prompt in crontab, which is awkward to maintain regardless. |

Both "remove" one-offs are un-commented (unlike their siblings), so nothing currently marks them as done or safe to ignore — that's the actual defect being fixed here, not just tidiness.

## Proposed crontab after cleanup

```cron
0 3 * * * /usr/local/bin/check-security.sh > /home/samba/share/slomix_discord/logs/cron-security-check.log 2>&1

15 4 */4 * * /home/samba/backups/backup_etlegacy.sh >> /home/samba/backups/backup.log 2>&1
```

## Owner-gated step (not performed by this PR)

```bash
crontab -e   # remove all 7 lines identified above (5 already-commented clutter
             # + 2 uncommented Feb one-offs), keep the 2 production lines
```

## Verify

```bash
crontab -l   # no Feb-dated one-offs, no commented "REMOVE AFTER USE" clutter;
             # check-security.sh (daily) and backup_etlegacy.sh (day-of-month
             # 1/5/9/.../29 schedule, see cadence note above) unchanged
```
