\set ON_ERROR_STOP on

begin;

insert into auth.users(id) values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
insert into public.farms(id, name) values
  ('11111111-1111-4111-8111-111111111111', 'North field'),
  ('99999999-9999-4999-8999-999999999999', 'Other field');
insert into public.farm_memberships(farm_id, user_id, role) values
  ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'owner'),
  ('11111111-1111-4111-8111-111111111111', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'member');
insert into public.devices(id, farm_id, label) values
  ('22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111', 'edge-1');

insert into public.telemetry_readings(
  message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
  recorded_at
) values (
  '33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  1, 'soil_moisture', 65.2, '%', 'valid', '2026-09-23T08:00:00Z'
);

insert into public.device_status_events(
  message_id, farm_id, device_id, schema_version, online, pump_state, health,
  recorded_at, uptime_seconds, firmware_version, errors
) values (
  '44444444-4444-4444-8444-444444444444',
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  1, true, false, 'healthy', '2026-09-23T08:00:00Z', 30, '0.1.0', '{}'
);

insert into public.command_acknowledgements(
  acknowledgement_id, command_id, farm_id, device_id, schema_version, status,
  occurred_at, pump_state
) values (
  '55555555-5555-4555-8555-555555555555',
  '66666666-6666-4666-8666-666666666666',
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  1, 'accepted', '2026-09-23T08:00:01Z', true
);

insert into public.irrigation_results(
  event_id, farm_id, device_id, schema_version, soil_moisture_before,
  soil_moisture_after, delta, result, completed_at
) values (
  '77777777-7777-4777-8777-777777777777',
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  1, 40.0, 45.2, 5.2, 'increased', '2026-09-23T08:01:00Z'
);

do $$
declare initial_time timestamptz;
begin
  select updated_at into initial_time from public.devices
  where id = '22222222-2222-4222-8222-222222222222';
  update public.devices set label = 'edge-main'
  where id = '22222222-2222-4222-8222-222222222222';
  if (select updated_at from public.devices
      where id = '22222222-2222-4222-8222-222222222222') < initial_time then
    raise exception 'updated_at moved backwards';
  end if;
end $$;

do $$ begin
  insert into public.farm_memberships(farm_id, user_id, role) values
    ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'owner');
  raise exception 'duplicate membership was accepted';
exception when unique_violation then null; end $$;

do $$ begin
  insert into public.farm_memberships(farm_id, user_id, role) values
    ('99999999-9999-4999-8999-999999999999', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'admin');
  raise exception 'invalid membership role was accepted';
exception when check_violation then null; end $$;

do $$ begin
  insert into public.devices(id, farm_id) values
    ('88888888-8888-4888-8888-888888888888', '12121212-1212-4212-8212-121212121212');
  raise exception 'device with missing farm was accepted';
exception when foreign_key_violation then null; end $$;

do $$ begin
  insert into public.telemetry_readings values (
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'soil_moisture', 65.2, '%', 'valid', now(), now()
  );
  raise exception 'duplicate telemetry was accepted';
exception when unique_violation then null; end $$;

do $$ begin
  insert into public.telemetry_readings(
    message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
    recorded_at
  ) values (
    '88888888-8888-4888-8888-888888888881',
    '99999999-9999-4999-8999-999999999999',
    '22222222-2222-4222-8222-222222222222',
    1, 'temperature', 22, '°C', 'valid', now()
  );
  raise exception 'cross-farm device telemetry was accepted';
exception when foreign_key_violation then null; end $$;

do $$ begin
  insert into public.telemetry_readings(
    message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
    recorded_at
  ) values (
    '88888888-8888-4888-8888-888888888882',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'temperature', 'NaN', '%', 'valid', now()
  );
  raise exception 'invalid telemetry was accepted';
exception when check_violation then null; end $$;

do $$ begin
  insert into public.telemetry_readings(
    message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
    recorded_at
  ) values (
    '88888888-8888-4888-8888-888888888886',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    2, 'temperature', 22, '°C', 'valid', now()
  );
  raise exception 'unsupported schema version was accepted';
exception when check_violation then null; end $$;

do $$ begin
  insert into public.telemetry_readings(
    message_id, farm_id, device_id, schema_version, metric, value, unit, quality,
    recorded_at
  ) values (
    '88888888-8888-4888-8888-888888888887',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'temperature', null, '°C', 'valid', now()
  );
  raise exception 'NULL telemetry value was accepted';
exception when not_null_violation then null; end $$;

do $$ begin
  insert into public.command_acknowledgements(
    acknowledgement_id, command_id, farm_id, device_id, schema_version, status,
    occurred_at
  ) values (
    '88888888-8888-4888-8888-888888888883',
    '66666666-6666-4666-8666-666666666666',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'failed', now()
  );
  raise exception 'failed ACK without reason was accepted';
exception when check_violation then null; end $$;

do $$ begin
  insert into public.irrigation_results(
    event_id, farm_id, device_id, schema_version, soil_moisture_before,
    soil_moisture_after, delta, result, completed_at
  ) values (
    '88888888-8888-4888-8888-888888888884',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 40, 45, 4, 'decreased', now()
  );
  raise exception 'inconsistent irrigation result was accepted';
exception when check_violation then null; end $$;

do $$ begin
  delete from public.devices
  where id = '22222222-2222-4222-8222-222222222222';
  raise exception 'device history was cascade-deleted';
exception when foreign_key_violation then null; end $$;

do $$ begin
  delete from public.farms
  where id = '11111111-1111-4111-8111-111111111111';
  raise exception 'farm with device/history was deleted';
exception when foreign_key_violation then null; end $$;

do $$ begin
  insert into public.device_status_events(
    message_id, farm_id, device_id, schema_version, online, pump_state, health,
    recorded_at, uptime_seconds, firmware_version, errors
  ) values (
    '88888888-8888-4888-8888-888888888885',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, false, false, 'degraded', now(), 0, '0.1.0', array['Bad Code']
  );
  raise exception 'invalid device error code was accepted';
exception when check_violation then null; end $$;

do $$ begin
  if (select ingested_at is null from public.telemetry_readings
      where message_id = '33333333-3333-4333-8333-333333333333') then
    raise exception 'server ingestion timestamp was not generated';
  end if;
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'telemetry_readings'
      and column_name in ('password', 'credential', 'payload')
  ) then
    raise exception 'forbidden opaque/secret telemetry column exists';
  end if;
end $$;

delete from auth.users where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
do $$ begin
  if exists (
    select 1 from public.farm_memberships
    where user_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
  ) then
    raise exception 'deleted user membership was retained';
  end if;
  if not exists (
    select 1 from public.farms
    where id = '11111111-1111-4111-8111-111111111111'
  ) then
    raise exception 'deleting user deleted the farm';
  end if;
end $$;

do $$ begin
  if exists (
    select 1 from pg_class
    where relnamespace = 'public'::regnamespace
      and relname in (
        'farms', 'farm_memberships', 'devices', 'telemetry_readings',
        'device_status_events', 'command_acknowledgements', 'irrigation_results'
      )
      and relrowsecurity
  ) then
    raise exception 'AGM-010 must not enable RLS';
  end if;
end $$;

rollback;
