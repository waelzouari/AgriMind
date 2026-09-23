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
