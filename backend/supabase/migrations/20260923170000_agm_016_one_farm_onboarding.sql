-- AGM-016: controlled, idempotent one-farm MVP onboarding.
-- Direct authenticated writes remain forbidden by AGM-011.

create function public.create_farm_for_current_user(farm_name text)
returns table (
  id uuid,
  name text,
  created_at timestamptz,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_user_id uuid := auth.uid();
  normalized_name text := btrim(farm_name);
  configured_farm public.farms%rowtype;
begin
  if current_user_id is null then
    raise exception using
      errcode = '42501',
      message = 'authentication_required';
  end if;

  if normalized_name is null or normalized_name = '' then
    raise exception using
      errcode = '22023',
      message = 'invalid_farm_name';
  end if;

  if char_length(normalized_name) > 120 then
    raise exception using
      errcode = '22023',
      message = 'invalid_farm_name';
  end if;

  -- Serialize this onboarding workflow per authenticated user without adding
  -- a global one-farm constraint that would prevent future multi-farm work.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(current_user_id::text, 0)
  );

  select farm.*
    into configured_farm
  from public.farm_memberships as membership
  join public.farms as farm on farm.id = membership.farm_id
  where membership.user_id = current_user_id
  order by membership.created_at, farm.created_at, farm.id
  limit 1;

  if found then
    return query select
      configured_farm.id,
      configured_farm.name,
      configured_farm.created_at,
      configured_farm.updated_at;
    return;
  end if;

  insert into public.farms(id, name)
  values (pg_catalog.gen_random_uuid(), normalized_name)
  returning public.farms.* into configured_farm;

  insert into public.farm_memberships(farm_id, user_id, role)
  values (configured_farm.id, current_user_id, 'owner');

  return query select
    configured_farm.id,
    configured_farm.name,
    configured_farm.created_at,
    configured_farm.updated_at;
end;
$$;

revoke all on function public.create_farm_for_current_user(text) from public;
revoke all on function public.create_farm_for_current_user(text) from anon;
grant execute on function public.create_farm_for_current_user(text)
  to authenticated;

comment on function public.create_farm_for_current_user(text) is
  'Atomically creates the current user owner farm once for AGM-016 onboarding.';
