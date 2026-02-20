# Security Policy

## Supported Versions

Security fixes are applied to the `main` branch and latest tagged release line.

## Reporting a Vulnerability

1. Do not open public issues for vulnerabilities.
2. Use GitHub private vulnerability reporting (Security tab) or contact maintainers directly.
3. Include affected component, reproduction steps, and impact assessment.

## Secret Management

- Keep credentials in environment variables only.
- Never commit `.env` files or tokens.
- Rotate compromised credentials immediately.
- Review `docs/SECRETS_MANAGEMENT.md` for full operational guidance.

## Response Process

1. Acknowledge report.
2. Reproduce and triage severity.
3. Patch and verify.
4. Release with advisory and remediation notes.
