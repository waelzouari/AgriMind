# Development conventions

## Prerequisites

- Git
- Python 3.11 or newer for foundation tooling
- `make`

Flutter, Supabase CLI, Mosquitto, and Raspberry Pi dependencies are introduced
only by their owning tickets.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
make bootstrap
make check
```

Copy `.env.example` to `.env` only when runtime configuration is needed. The
local `.env` is ignored. Never store real credentials in documentation,
fixtures, screenshots, issue bodies, or commit history.

## Documentation

- Architecture: `docs/architecture/`
- Durable decisions: `docs/adrs/`
- Protocols: `docs/mqtt/` and later `docs/api/`
- Planning and scope: `docs/planning/`
- Verification strategy and evidence: `docs/testing/`

Documentation changes follow the same issue, review, and CI process as code.
Use Mermaid for diagrams that should remain diffable. Record only tests that
were actually executed.
