-- AGM-011: user-facing authorization and farm isolation.
-- Trusted ingestion remains server-side and Storage is intentionally deferred.

create schema if not exists private;
revoke all on schema private from public;

create function private.is_farm_member(target_farm_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.farm_memberships as membership
    where membership.farm_id = target_farm_id
      and membership.user_id = auth.uid()
  );
$$;

create function private.is_farm_owner(target_farm_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.farm_memberships as membership
    where membership.farm_id = target_farm_id
      and membership.user_id = auth.uid()
      and membership.role = 'owner'
  );
$$;

revoke all on function private.is_farm_member(uuid) from public;
revoke all on function private.is_farm_owner(uuid) from public;
grant usage on schema private to authenticated;
grant execute on function private.is_farm_member(uuid) to authenticated;
grant execute on function private.is_farm_owner(uuid) to authenticated;

alter table public.farms enable row level security;
alter table public.farm_memberships enable row level security;
alter table public.devices enable row level security;
alter table public.telemetry_readings enable row level security;
alter table public.device_status_events enable row level security;
alter table public.command_acknowledgements enable row level security;
alter table public.irrigation_results enable row level security;

revoke all on table public.farms from public, anon, authenticated;
revoke all on table public.farm_memberships from public, anon, authenticated;
revoke all on table public.devices from public, anon, authenticated;
revoke all on table public.telemetry_readings from public, anon, authenticated;
revoke all on table public.device_status_events from public, anon, authenticated;
revoke all on table public.command_acknowledgements from public, anon, authenticated;
revoke all on table public.irrigation_results from public, anon, authenticated;

grant all on table public.farms to service_role;
grant all on table public.farm_memberships to service_role;
grant all on table public.devices to service_role;
grant all on table public.telemetry_readings to service_role;
grant all on table public.device_status_events to service_role;
grant all on table public.command_acknowledgements to service_role;
grant all on table public.irrigation_results to service_role;

grant select on table public.farms to authenticated;
grant update (name) on table public.farms to authenticated;
grant delete on table public.farms to authenticated;
grant select on table public.farm_memberships to authenticated;
grant select on table public.devices to authenticated;
grant select on table public.telemetry_readings to authenticated;
grant select on table public.device_status_events to authenticated;
grant select on table public.command_acknowledgements to authenticated;
grant select on table public.irrigation_results to authenticated;

create policy farms_select_member
on public.farms for select to authenticated
using (private.is_farm_member(id));

create policy farms_update_owner
on public.farms for update to authenticated
using (private.is_farm_owner(id))
with check (private.is_farm_owner(id));

create policy farms_delete_owner
on public.farms for delete to authenticated
using (private.is_farm_owner(id));

create policy farm_memberships_select_self_or_owner
on public.farm_memberships for select to authenticated
using (
  user_id = auth.uid()
  or private.is_farm_owner(farm_id)
);

create policy devices_select_member
on public.devices for select to authenticated
using (private.is_farm_member(farm_id));

create policy telemetry_readings_select_member
on public.telemetry_readings for select to authenticated
using (private.is_farm_member(farm_id));

create policy device_status_events_select_member
on public.device_status_events for select to authenticated
using (private.is_farm_member(farm_id));

create policy command_acknowledgements_select_member
on public.command_acknowledgements for select to authenticated
using (private.is_farm_member(farm_id));

create policy irrigation_results_select_member
on public.irrigation_results for select to authenticated
using (private.is_farm_member(farm_id));

comment on schema private is
  'Non-API helper functions used by row-level security policies.';
comment on function private.is_farm_member(uuid) is
  'Checks auth.uid() membership without accepting a caller-supplied user identity.';
comment on function private.is_farm_owner(uuid) is
  'Checks auth.uid() ownership without accepting a caller-supplied user identity.';
