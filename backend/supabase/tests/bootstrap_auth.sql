-- Standalone PostgreSQL harness only. Supabase already supplies auth.users.
create schema auth;
create table auth.users (
  id uuid primary key
);
