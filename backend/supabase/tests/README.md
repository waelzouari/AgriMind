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

The harness then applies AGM-016 and verifies the restricted onboarding RPC,
identity derivation, name normalization, atomic farm/owner creation, retry
idempotence, cross-farm isolation, and continued denial of direct writes. It
also runs two overlapping PostgreSQL sessions for the same user and verifies
that the transaction advisory lock yields one farm and one owner membership.
