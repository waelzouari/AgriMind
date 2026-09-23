# Supabase tests

`agm_010_schema_test.sql` exercises the relational constraints against a real
PostgreSQL database before RLS is installed. `agm_011_rls_test.sql` then tests
all seven application tables as anonymous, authenticated owner/member,
authenticated non-member, cross-farm, and trusted server roles.

`bootstrap_auth.sql` supplies only the minimal Supabase roles, `auth.users`, and
`auth.uid()` behavior required outside Supabase. It is test infrastructure and
is never deployed as a migration. Test identities are fixed synthetic UUIDs;
the suite needs no Supabase project or credentials.

Run `make db-test`. The harness creates and removes two uniquely named databases
to prove clean reset/reproduction. It applies AGM-010, runs the AGM-010 tests,
then applies AGM-011 and runs the authorization/isolation tests.
It finally applies AGM-012 and verifies restricted RPC privileges, registered
active-device enforcement, farm authority, duplicate/conflict behavior, status
ingestion, and preservation of authenticated-client write denial.
