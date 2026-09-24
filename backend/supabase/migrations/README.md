# Supabase migrations

Database changes are ordered, immutable SQL migrations beginning with AGM-010.
The repository is the schema source of truth; do not maintain a remote project
through undocumented Dashboard changes.

With Supabase CLI installed:

```bash
supabase db reset --workdir backend
supabase test db --workdir backend
```

The repository also validates the migration twice from clean disposable
PostgreSQL databases:

```bash
make db-test
```

AGM-010 defines relations and constraints only. AGM-011 adds Auth-backed RLS
and grants without changing the AGM-010 migration. Authenticated clients can
read only farms where `auth.uid()` has a membership; only owners can rename or
delete their farm. Memberships, devices, and event ingestion have no direct
authenticated write path.

AGM-011 intentionally creates no Storage bucket because the P0 data flows use
structured records only. A private, farm-scoped bucket belongs with the P1
Computer Vision capability when file storage is actually required. Secure
device provisioning and ingestion remain AGM-012 work.

AGM-012 adds service-role-only telemetry and device-status RPCs. They lock and
authorize the registered device, derive its authoritative farm, preserve
primary-key idempotency, detect conflicting reuse of a message ID, and update
`last_seen_at` only after a new accepted event. AGM-011 policies and grants for
anonymous/authenticated clients remain unchanged.

AGM-016 adds `public.create_farm_for_current_user(text)` as the only
authenticated farm-creation path. The `SECURITY DEFINER` RPC derives identity
from `auth.uid()`, takes neither a user ID nor a role, trims and bounds the farm
name, and atomically inserts the farm plus its owner membership. A
transaction-scoped advisory lock derived from the authenticated user serializes
concurrent onboarding attempts; after taking the lock the function returns an
existing membership before creating anything. This makes the MVP workflow
idempotent without imposing a permanent one-farm database constraint. Direct
authenticated inserts and all AGM-011 RLS policies remain unchanged.

AGM-019 provisionally adds nullable paired latitude/longitude columns to
`farms`, with owner-only updates through the existing RLS policy and
column-level grants. It also adds the service-written, member-readable
`weather_snapshots` cache with one row per farm. The 30-minute fresh lifetime,
6-hour maximum stale age, UTC units, and Open-Meteo fields are TecWeek MVP
implementation defaults subject to later architecture/product review.

AGM-028 adds the farm-scoped `trees` inventory and its owner-write/member-read
RLS policies. It does not add Farm Manager UI, Computer Vision state, or
production seed data.
