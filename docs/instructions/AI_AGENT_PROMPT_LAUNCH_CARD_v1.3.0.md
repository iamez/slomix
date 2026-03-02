# Slomix Mega Prompt Launch Card (v1.3.0)

Use this card to start any execution agent without ambiguity.

## Canonical Target

- File: `docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md`
- Version: `2026.02.19-v1.3.0`
- Lock ID: `SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19`

## Profile Selector

- `Profile A`: full audit + hardening (Gate A then Gate B).
- `Profile B`: targeted system-log follow-up only.

## Paste This To The Agent (Profile A)

```md
Execute only this plan:
- File: docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md
- Version: 2026.02.19-v1.3.0
- Lock ID: SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19
- Profile: A

Rules:
- Do not use any other prompt unless I explicitly approve it.
- If file/version/lock/profile mismatch exists, stop and ask me.
- Start with Context Sync + Baseline Drift Snapshot.
- Deliver Gate A outputs only first (no code changes).

Reply first with:
ACK LOCK <lock-id> | PROFILE <A/B> | MODE <gate-a-only>
```

## Paste This To The Agent (Profile B)

```md
Execute only this plan:
- File: docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md
- Version: 2026.02.19-v1.3.0
- Lock ID: SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19
- Profile: B

Rules:
- Do not use any other prompt unless I explicitly approve it.
- If file/version/lock/profile mismatch exists, stop and ask me.
- Use only the Profile B scope from the prompt.
- Keep evidence bundle strict (code + tests + logs + DB where relevant).

Reply first with:
ACK LOCK <lock-id> | PROFILE <A/B> | MODE <targeted-exec>
```
