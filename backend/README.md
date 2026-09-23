# Backend

Cloud persistence and server-side services live here. Supabase migrations,
functions, and tests are version controlled under `supabase/`; independently
deployed ingestion or inference services live under `services/` when their
owning tickets begin.

AGM-010 introduces the first relational schema migration under
`supabase/migrations/`. It deliberately contains no RLS policy, ingestion
service, privileged credential, or application API.
