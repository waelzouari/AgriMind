# Supabase tests

`agm_010_schema_test.sql` exercises the relational constraints against a real
PostgreSQL database. `bootstrap_auth.sql` supplies only the minimal
`auth.users` stub required outside Supabase; it is never deployed as a
migration.

Run `make db-test`. The harness creates and removes two uniquely named databases
to prove clean reset/reproduction. AGM-011 will add RLS, Auth, Storage, and
cross-user isolation tests.
