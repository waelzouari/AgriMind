\set ON_ERROR_STOP on

begin;

insert into auth.users(id) values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
  ('abababab-abab-4bab-8bab-abababababab'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
  ('cccccccc-cccc-4ccc-8ccc-cccccccccccc');

-- Trusted setup represents administrative provisioning and future ingestion.
-- Auth users themselves are created by Supabase Auth, not by service_role.
set local role service_role;

insert into public.farms(id, name) values
  ('11111111-1111-4111-8111-111111111111', 'Farm A'),
  ('99999999-9999-4999-8999-999999999999', 'Farm B');

insert into public.farm_memberships(farm_id, user_id, role) values
  ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'owner'),
  ('11111111-1111-4111-8111-111111111111', 'abababab-abab-4bab-8bab-abababababab', 'member'),
  ('99999999-9999-4999-8999-999999999999', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'owner');

insert into public.devices(id, farm_id, label) values
  ('22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111', 'Device A'),
  ('88888888-8888-4888-8888-888888888888', '99999999-9999-4999-8999-999999999999', 'Device B');

insert into public.telemetry_readings(
  message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
  recorded_at
) values
  ('31000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', 1, 'temperature', 22, '°C', 'valid', now()),
  ('39000000-0000-4000-8000-000000000009', '99999999-9999-4999-8999-999999999999', '88888888-8888-4888-8888-888888888888', 1, 'temperature', 24, '°C', 'valid', now());

insert into public.device_status_events(
  message_id, farm_id, device_id, schema_version, online, pump_state, health,
  recorded_at, uptime_seconds, firmware_version
) values
  ('41000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', 1, true, false, 'healthy', now(), 10, '0.1.0'),
  ('49000000-0000-4000-8000-000000000009', '99999999-9999-4999-8999-999999999999', '88888888-8888-4888-8888-888888888888', 1, true, false, 'healthy', now(), 10, '0.1.0');

insert into public.command_acknowledgements(
  acknowledgement_id, command_id, farm_id, device_id, schema_version, status,
  occurred_at, pump_state
) values
  ('51000000-0000-4000-8000-000000000001', '61000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', 1, 'accepted', now(), true),
  ('59000000-0000-4000-8000-000000000009', '69000000-0000-4000-8000-000000000009', '99999999-9999-4999-8999-999999999999', '88888888-8888-4888-8888-888888888888', 1, 'accepted', now(), true);

insert into public.irrigation_results(
  event_id, farm_id, device_id, schema_version, soil_moisture_before,
  soil_moisture_after, delta, result, completed_at
) values
  ('71000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', 1, 40, 45, 5, 'increased', now()),
  ('79000000-0000-4000-8000-000000000009', '99999999-9999-4999-8999-999999999999', '88888888-8888-4888-8888-888888888888', 1, 40, 45, 5, 'increased', now());

reset role;

do $$
declare
  secured_tables integer;
  write_grants integer;
begin
  select count(*) into secured_tables
  from pg_class
  where relnamespace = 'public'::regnamespace
    and relname in (
      'farms', 'farm_memberships', 'devices', 'telemetry_readings',
      'device_status_events', 'command_acknowledgements', 'irrigation_results'
    )
    and relrowsecurity;
  if secured_tables <> 7 then
    raise exception 'expected RLS on 7 application tables, found %', secured_tables;
  end if;

  select count(*) into write_grants
  from information_schema.table_privileges
  where grantee = 'authenticated'
    and table_schema = 'public'
    and table_name in (
      'farm_memberships', 'devices', 'telemetry_readings',
      'device_status_events', 'command_acknowledgements', 'irrigation_results'
    )
    and privilege_type in ('INSERT', 'UPDATE', 'DELETE');
  if write_grants <> 0 then
    raise exception 'authenticated received forbidden direct write grants';
  end if;

  if not (
    select prosecdef and coalesce(proconfig, '{}') @> array['search_path=""']
    from pg_proc
    where oid = 'private.is_farm_member(uuid)'::regprocedure
  ) then
    raise exception 'membership helper is not safely configured';
  end if;
  if not (
    select prosecdef and coalesce(proconfig, '{}') @> array['search_path=""']
    from pg_proc
    where oid = 'private.is_farm_owner(uuid)'::regprocedure
  ) then
    raise exception 'owner helper is not safely configured';
  end if;
  if has_function_privilege('anon', 'private.is_farm_member(uuid)', 'EXECUTE')
     or has_function_privilege('anon', 'private.is_farm_owner(uuid)', 'EXECUTE') then
    raise exception 'anonymous role can execute private authorization helpers';
  end if;
end $$;

-- Anonymous callers have no table access at all.
set local role anon;
select set_config('request.jwt.claim.sub', '', true);
do $$ begin
  perform count(*) from public.farms;
  raise exception 'anonymous farm read was accepted';
exception when insufficient_privilege then null; end $$;
reset role;

-- Farm A owner sees only Farm A, including every membership in that farm.
set local role authenticated;
select set_config('request.jwt.claim.sub', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
do $$ begin
  if (select count(*) from public.farms) <> 1 then
    raise exception 'Farm A owner did not see exactly one farm';
  end if;
  if exists (select 1 from public.farms where id = '99999999-9999-4999-8999-999999999999') then
    raise exception 'Farm A owner read Farm B';
  end if;
  if (select count(*) from public.farm_memberships) <> 2 then
    raise exception 'Farm A owner did not see the Farm A membership list';
  end if;
  if (select count(*) from public.devices) <> 1
     or (select count(*) from public.telemetry_readings) <> 1
     or (select count(*) from public.device_status_events) <> 1
     or (select count(*) from public.command_acknowledgements) <> 1
     or (select count(*) from public.irrigation_results) <> 1 then
    raise exception 'Farm A owner event/device isolation failed';
  end if;
end $$;

update public.farms set name = 'Farm A renamed'
where id = '11111111-1111-4111-8111-111111111111';
do $$ begin
  if not exists (select 1 from public.farms where name = 'Farm A renamed') then
    raise exception 'Farm A owner could not update own farm name';
  end if;
end $$;

update public.farms set name = 'forbidden'
where id = '99999999-9999-4999-8999-999999999999';
reset role;
do $$ begin
  if (select name from public.farms where id = '99999999-9999-4999-8999-999999999999') <> 'Farm B' then
    raise exception 'Farm A owner updated Farm B';
  end if;
end $$;

-- Farm B's owner has the symmetric view and cannot observe Farm A.
set local role authenticated;
select set_config('request.jwt.claim.sub', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true);
do $$ begin
  if (select count(*) from public.farms) <> 1
     or not exists (
       select 1 from public.farms
       where id = '99999999-9999-4999-8999-999999999999'
     )
     or (select count(*) from public.devices) <> 1
     or (select count(*) from public.telemetry_readings) <> 1 then
    raise exception 'Farm B owner isolation failed';
  end if;
end $$;
reset role;

-- Members can read their farm data and only their own membership row.
set local role authenticated;
select set_config('request.jwt.claim.sub', 'abababab-abab-4bab-8bab-abababababab', true);
do $$ begin
  if (select count(*) from public.farms) <> 1
     or (select count(*) from public.farm_memberships) <> 1
     or (select count(*) from public.devices) <> 1
     or (select count(*) from public.telemetry_readings) <> 1 then
    raise exception 'member read isolation failed';
  end if;
end $$;
update public.farms set name = 'member write'
where id = '11111111-1111-4111-8111-111111111111';
reset role;
do $$ begin
  if (select name from public.farms where id = '11111111-1111-4111-8111-111111111111') <> 'Farm A renamed' then
    raise exception 'member updated farm';
  end if;
end $$;

-- An authenticated user without a membership sees no application rows.
set local role authenticated;
select set_config('request.jwt.claim.sub', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', true);
do $$ begin
  if (select count(*) from public.farms) <> 0
     or (select count(*) from public.farm_memberships) <> 0
     or (select count(*) from public.devices) <> 0
     or (select count(*) from public.telemetry_readings) <> 0
     or (select count(*) from public.device_status_events) <> 0
     or (select count(*) from public.command_acknowledgements) <> 0
     or (select count(*) from public.irrigation_results) <> 0 then
    raise exception 'non-member read application data';
  end if;
end $$;

do $$ begin
  insert into public.farm_memberships(farm_id, user_id, role) values
    ('99999999-9999-4999-8999-999999999999', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'owner');
  raise exception 'non-member created a privileged membership';
exception when insufficient_privilege then null; end $$;

do $$ begin
  insert into public.farms(id, name) values
    ('12121212-1212-4212-8212-121212121212', 'Orphan farm');
  raise exception 'authenticated direct farm creation was accepted';
exception when insufficient_privilege then null; end $$;

do $$ begin
  insert into public.telemetry_readings(
    message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
    recorded_at
  ) values (
    '32000000-0000-4000-8000-000000000002',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'humidity', 50, '%', 'valid', now()
  );
  raise exception 'authenticated direct event ingestion was accepted';
exception when insufficient_privilege then null; end $$;
reset role;

-- Existing members cannot promote themselves or mutate governance records.
set local role authenticated;
select set_config('request.jwt.claim.sub', 'abababab-abab-4bab-8bab-abababababab', true);
do $$ begin
  update public.farm_memberships set role = 'owner'
  where farm_id = '11111111-1111-4111-8111-111111111111'
    and user_id = 'abababab-abab-4bab-8bab-abababababab';
  raise exception 'member self-promotion was accepted';
exception when insufficient_privilege then null; end $$;
do $$ begin
  delete from public.farm_memberships
  where farm_id = '11111111-1111-4111-8111-111111111111';
  raise exception 'member deleted membership records';
exception when insufficient_privilege then null; end $$;
reset role;

-- The trusted role can still provision and ingest without exposing that power
-- to authenticated or anonymous clients.
set local role service_role;
insert into public.telemetry_readings(
  message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
  recorded_at
) values (
  '32000000-0000-4000-8000-000000000002',
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  1, 'humidity', 50, '%', 'valid', now()
);
reset role;

rollback;
