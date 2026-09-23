# Cloud data model

AGM-010 establishes the relational Supabase/PostgreSQL schema for the MVP. It
does not expose tables to clients: Auth/RLS/Storage belong to AGM-011 and secure
device ingestion belongs to AGM-012.

```text
auth.users ──< farm_memberships >── farms ──< devices
                                              ├── telemetry_readings
                                              ├── device_status_events
                                              ├── command_acknowledgements
                                              └── irrigation_results
```

Memberships support multiple users per farm and multiple farms per user. Event
rows retain both contract `farm_id` and `device_id`; a composite foreign key
proves the device belongs to that farm and gives future RLS a direct farm key.

Canonical v1 identifiers are primary keys: telemetry/status `message_id`, ACK
`acknowledgement_id`, and irrigation `event_id`. This makes AGM-008/009
at-least-once republication safe for a future ingestion service using conflict
handling. `command_id` is correlation data only and never authorizes or
executes a pump command.

Device timestamps (`recorded_at`, `occurred_at`, `completed_at`) are retained
alongside server `ingested_at`. PostgreSQL `timestamptz` represents instants;
clients must serialize them as UTC. No telemetry range is invented beyond the
v1 contract, while metric/unit, finite-number, schema-version, ACK semantic,
and irrigation-result constraints mirror existing contracts.

Deletion is conservative. Removing a user deletes memberships only. Farm and
device deletion is restricted while dependent device/history rows exist;
historical physical events are never silently cascade-deleted.

RLS is intentionally not enabled by AGM-010. Until AGM-011 installs and tests
policies and grants, these tables must not be exposed directly to Flutter.
