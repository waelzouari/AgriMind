# Cloud data model

AGM-010 establishes the relational Supabase/PostgreSQL schema for the MVP.
AGM-011 adds the user-facing authorization boundary, while secure device
ingestion remains AGM-012 work.

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

## Auth and row-level security

Supabase Auth is the identity authority. Policies derive the current user only
from `auth.uid()` and resolve farm authorization through
`farm_memberships`; client-controlled profile metadata and payload user IDs are
not authorization inputs.

RLS is enabled on all seven application tables. Anonymous clients have no table
access. Authenticated owners and members can read only their farms, devices,
and event history. Members see only their own membership row, while an owner
can see the membership list for their farm. Only owners may rename or delete a
farm, and existing foreign keys continue to protect retained device history.

There is intentionally no direct authenticated write path for farms,
memberships, devices, or event rows, except for the owner's narrowly scoped
farm-name update and constrained delete. In particular:

- initial farm creation and its owner membership require a future atomic,
  trusted onboarding operation;
- membership and ownership changes require a trusted operation that prevents
  self-promotion and loss of ownership;
- device provisioning and all telemetry/status/ACK/irrigation ingestion are
  reserved for trusted server-side components introduced by later tickets.

The RLS membership helpers are `SECURITY DEFINER` only to avoid recursive
membership policies. They accept a farm ID but never a caller-supplied user ID,
use an empty `search_path`, fully qualify referenced objects, and expose execute
permission only to `authenticated`.

Flutter will use only the public Supabase URL, the public anon/publishable key,
and the signed-in user's JWT. The `service_role`, database passwords, JWT
secrets, and migration credentials are server/CI secrets and must never be
placed in Flutter, on the Raspberry Pi, or in Git. Cloud authorization does not
replace the Raspberry Pi pump safety gate.

## Storage decision

AGM-011 creates no Storage bucket. The P0 flows persist structured records and
have no file-storage requirement. Creating an unused bucket would add policy
surface without delivering an MVP capability.

Storage is deferred to the P1 Computer Vision flow. That capability must add a
private bucket through a versioned migration, use farm-scoped object paths such
as `{farm_id}/inspections/{asset_id}`, and test the same cross-farm isolation
before exposing uploads or signed reads. No public bucket is currently part of
the architecture.
