# Backend

Cloud persistence and server-side services live here. Supabase migrations,
functions, and tests are version controlled under `supabase/`; independently
deployed ingestion or inference services live under `services/` when their
owning tickets begin.

AGM-010 introduces the relational schema, AGM-011 adds client-facing RLS, and
AGM-012 adds restricted trusted-ingestion RPCs plus the independently deployed
service under `services/ingestion/`. Privileged runtime values are never stored
in this repository.
