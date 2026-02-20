# Research Intake and Validation

Use this folder to process external research before it affects audit plans or the master prompt.

## Folders

- `docs/research/inbox/`: raw, unverified research dumps.
- `docs/research/validated/`: verified summaries after evidence cross-checking.

## Naming

- Inbox: `RESEARCH_INBOX_<date>_<source>.md`
- Validated: `RESEARCH_VALIDATED_<date>.md`

## Rule

No claim from `inbox` can be treated as fact until it is marked `verified` or `partially-verified` using the protocol in:

- `docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md`
