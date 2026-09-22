# AgriMind

AgriMind is a TecWeek 3.0 agritech MVP that connects Raspberry Pi sensors,
safe irrigation control, MQTT, Supabase, weather intelligence, and a Flutter
mobile application.

This repository contains the approved monorepo foundation. Product feature
implementation has not started.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
make bootstrap
make check
```

## Planning documents

- [Discovery report](docs/planning/discovery-report.md)
- [System architecture](docs/architecture/system-overview.md)
- [Edge hardware architecture](docs/architecture/edge.md)
- [Dependency-aware backlog](docs/planning/backlog.md)
- [MQTT contract](docs/mqtt/topics.md)
- [Testing strategy](docs/testing/testing-strategy.md)
- [Development conventions](docs/development.md)
- [Contributing workflow](CONTRIBUTING.md)

## Scope guardrail

The autonomous inspection robot is future scope and is not part of the
TecWeek MVP.
