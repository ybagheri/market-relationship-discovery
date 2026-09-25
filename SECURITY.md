# Security Policy

## Reporting

Report vulnerabilities privately to the repository owner. Do not include account numbers, credentials, tokens, or personal data in a public issue.

## Credential handling

- Never commit `.env`, terminal databases, or account credentials.
- Store local machine paths only in the ignored `.env` file.
- Do not add password authentication support to the research adapter.
- Authenticate through the MetaTrader terminal UI.
- Review `git diff --cached` before every commit.

## Trading safety

The project has no order execution implementation. `demo_only` must remain enabled in sequential and parallel collection workers. A future execution system requires a separate design review, independent safety gates, exposure limits, kill switch, immutable audit records, and explicit real-account opt-in. Those controls are not provided by the current research code.

## Data safety

Raw market data and generated reports can be large or machine-specific and are excluded by default. Public reports should not contain account identifiers or private terminal details.
