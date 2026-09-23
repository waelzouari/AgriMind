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

AGM-010 defines relations and constraints only. RLS, grants, Auth lifecycle,
Storage, and ingestion functions belong to later tickets.
