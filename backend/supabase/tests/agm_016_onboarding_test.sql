\set ON_ERROR_STOP on

begin;

insert into auth.users(id) values
  ('dddddddd-dddd-4ddd-8ddd-dddddddddddd'),
  ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'),
  ('ffffffff-ffff-4fff-8fff-ffffffffffff');

do $$
declare
  function_arguments text;
begin
  select pg_get_function_identity_arguments(proc.oid)
    into function_arguments
  from pg_proc as proc
  where proc.oid = 'public.create_farm_for_current_user(text)'::regprocedure;

  if function_arguments <> 'farm_name text' then
    raise exception 'onboarding RPC accepts unexpected identity arguments: %',
      function_arguments;
  end if;

  if not (
    select prosecdef and coalesce(proconfig, '{}') @> array['search_path=""']
    from pg_proc
    where oid = 'public.create_farm_for_current_user(text)'::regprocedure
  ) then
    raise exception 'onboarding RPC is not SECURITY DEFINER with empty search_path';
  end if;

  if has_function_privilege(
      'public', 'public.create_farm_for_current_user(text)', 'EXECUTE'
    ) or has_function_privilege(
      'anon', 'public.create_farm_for_current_user(text)', 'EXECUTE'
    ) or not has_function_privilege(
      'authenticated', 'public.create_farm_for_current_user(text)', 'EXECUTE'
    ) then
    raise exception 'onboarding RPC execute permissions are unsafe';
  end if;
end $$;

set local role anon;
do $$ begin
  perform public.create_farm_for_current_user('Anonymous farm');
  raise exception 'anonymous onboarding invocation was accepted';
exception when insufficient_privilege then null; end $$;
reset role;

set local role authenticated;
select set_config('request.jwt.claim.sub', '', true);
do $$ begin
  perform public.create_farm_for_current_user('Invalid session farm');
  raise exception 'authenticated role without a user identity was accepted';
exception when insufficient_privilege then null; end $$;
reset role;

set local role authenticated;
select set_config(
  'request.jwt.claim.sub',
  'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  true
);

do $$
declare
  first_farm public.farms%rowtype;
  retry_farm public.farms%rowtype;
begin
  select * into first_farm
  from public.create_farm_for_current_user('  Ferme Démo  ');
  select * into retry_farm
  from public.create_farm_for_current_user('Ignored retry name');

  if first_farm.id <> retry_farm.id or retry_farm.name <> 'Ferme Démo' then
    raise exception 'onboarding retry did not return the configured farm';
  end if;
  if (select count(*) from public.farm_memberships
      where user_id = auth.uid() and role = 'owner') <> 1 then
    raise exception 'onboarding did not create exactly one owner membership';
  end if;
end $$;

do $$ begin
  perform public.create_farm_for_current_user('   ');
  raise exception 'blank farm name was accepted';
exception when invalid_parameter_value then null; end $$;

do $$ begin
  insert into public.farms(id, name) values
    ('16161616-1616-4616-8616-161616161616', 'Direct farm');
  raise exception 'authenticated direct farm insert was accepted';
exception when insufficient_privilege then null; end $$;

do $$ begin
  insert into public.farm_memberships(farm_id, user_id, role) values
    ('11111111-1111-4111-8111-111111111111', auth.uid(), 'owner');
  raise exception 'authenticated direct membership insert was accepted';
exception when insufficient_privilege then null; end $$;
reset role;

-- A separate user cannot observe the newly created farm.
set local role authenticated;
select set_config(
  'request.jwt.claim.sub',
  'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  true
);
do $$ begin
  if exists (select 1 from public.farms where name = 'Ferme Démo') then
    raise exception 'cross-farm read exposed the onboarded farm';
  end if;
end $$;
reset role;

-- A forced membership failure rolls the farm insert back with the RPC call.
create function public.reject_test_membership()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.user_id = 'ffffffff-ffff-4fff-8fff-ffffffffffff'::uuid then
    raise exception 'forced_membership_failure';
  end if;
  return new;
end;
$$;
create trigger reject_test_membership
before insert on public.farm_memberships
for each row execute function public.reject_test_membership();

set local role authenticated;
select set_config(
  'request.jwt.claim.sub',
  'ffffffff-ffff-4fff-8fff-ffffffffffff',
  true
);
do $$ begin
  perform public.create_farm_for_current_user('Must roll back');
  raise exception 'forced membership failure was not propagated';
exception when others then
  if sqlerrm <> 'forced_membership_failure' then raise; end if;
end $$;
reset role;

do $$ begin
  if exists (select 1 from public.farms where name = 'Must roll back') then
    raise exception 'farm insert survived failed owner membership creation';
  end if;
end $$;

rollback;
