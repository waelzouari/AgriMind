# Contributing

## Workflow

AgriMind uses the ADLC loop: analyze, design, plan, implement, test, review,
document, integrate, and iterate. Work one GitHub issue at a time.

1. Start from current `develop`.
2. Create `feature/AGM-XXX-description`, `fix/AGM-XXX-description`, or
   `docs/AGM-XXX-description`.
3. Keep the change within the issue scope and update tests/documentation.
4. Run `make check` before committing.
5. Open a pull request to `develop` using the repository template.
6. Release through a reviewed `develop` to `main` pull request.

Never commit credentials, `.env`, private keys, production certificates,
datasets without an approved licence, or generated model artifacts.

## Commit messages

Use a concise conventional prefix and reference the ticket, for example:

```text
chore(AGM-001): establish repository foundation
```

## Definition of Done

Acceptance criteria, tests, static checks, failure handling, documentation,
self-review, CI, and secret scanning must all pass. Hardware or model metrics are
reported only when they were actually measured.
