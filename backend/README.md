# Backend

Cloud persistence and server-side services live here. Supabase migrations,
functions, and tests are version controlled under `supabase/`; independently
deployed ingestion or inference services live under `services/` when their
owning tickets begin.

AGM-010 introduces the relational schema, AGM-011 adds client-facing RLS, and
AGM-012 adds restricted trusted-ingestion RPCs plus the independently deployed
service under `services/ingestion/`. AGM-019 adds the independently deployed
Open-Meteo aggregation and persistent cache worker under `services/weather/`.
Privileged runtime values are never stored in this repository.
