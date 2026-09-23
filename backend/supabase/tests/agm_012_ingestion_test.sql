\set ON_ERROR_STOP on

begin;

insert into auth.users(id) values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
set local role service_role;
insert into public.farms(id, name) values
  ('11111111-1111-4111-8111-111111111111', 'Farm A'),
  ('99999999-9999-4999-8999-999999999999', 'Farm B');
insert into public.farm_memberships(farm_id, user_id, role) values
  ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'owner');
insert into public.devices(id, farm_id, label, is_active) values
  ('22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111', 'active', true),
  ('88888888-8888-4888-8888-888888888888', '11111111-1111-4111-8111-111111111111', 'inactive', false);
reset role;

do $$ begin
  if not (
    select prosecdef and coalesce(proconfig, '{}') @> array['search_path=""']
    from pg_proc where oid = 'public.ingest_telemetry(uuid,uuid,uuid,integer,text,double precision,text,text,timestamptz)'::regprocedure
  ) then
    raise exception 'telemetry RPC security configuration is invalid';
  end if;
  if not (
    select prosecdef and coalesce(proconfig, '{}') @> array['search_path=""']
    from pg_proc where oid = 'public.ingest_device_status(uuid,uuid,uuid,integer,boolean,boolean,text,timestamptz,bigint,text,text[])'::regprocedure
  ) then
    raise exception 'status RPC security configuration is invalid';
  end if;
  if has_function_privilege('anon', 'public.ingest_telemetry(uuid,uuid,uuid,integer,text,double precision,text,text,timestamptz)', 'EXECUTE')
     or has_function_privilege('authenticated', 'public.ingest_telemetry(uuid,uuid,uuid,integer,text,double precision,text,text,timestamptz)', 'EXECUTE')
     or not has_function_privilege('service_role', 'public.ingest_telemetry(uuid,uuid,uuid,integer,text,double precision,text,text,timestamptz)', 'EXECUTE') then
    raise exception 'telemetry RPC privileges are invalid';
  end if;
end $$;

set local role anon;
do $$ begin
  perform public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  );
  raise exception 'anon executed telemetry RPC';
exception when insufficient_privilege then null; end $$;
reset role;

set local role authenticated;
select set_config('request.jwt.claim.sub', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
do $$ begin
  perform public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  );
  raise exception 'authenticated executed telemetry RPC';
exception when insufficient_privilege then null; end $$;
do $$ begin
  insert into public.telemetry_readings(
    message_id, farm_id, device_id, schema_version, metric, value, unit,
    quality, recorded_at
  ) values (
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  );
  raise exception 'authenticated inserted telemetry directly';
exception when insufficient_privilege then null; end $$;
reset role;

set local role service_role;
do $$ begin
  if public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  ) <> 'inserted' then
    raise exception 'first telemetry was not inserted';
  end if;
end $$;

update public.devices set last_seen_at = '2026-09-23T12:01:00Z'
where id = '22222222-2222-4222-8222-222222222222';
do $$ begin
  if public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  ) <> 'duplicate' then
    raise exception 'exact telemetry redelivery was not idempotent';
  end if;
  if (select count(*) from public.telemetry_readings) <> 1 then
    raise exception 'duplicate telemetry created a second row';
  end if;
  if (select last_seen_at from public.devices where id = '22222222-2222-4222-8222-222222222222') <> '2026-09-23T12:01:00Z' then
    raise exception 'duplicate telemetry changed last_seen_at';
  end if;
end $$;

do $$ begin
  perform public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, 'temperature', 99.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  );
  raise exception 'conflicting telemetry duplicate was accepted';
exception when raise_exception then
  if sqlerrm <> 'message_id_conflict' then raise; end if;
end $$;

do $$ begin
  perform public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333334',
    '99999999-9999-4999-8999-999999999999',
    '22222222-2222-4222-8222-222222222222', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  );
  raise exception 'cross-farm telemetry was accepted';
exception when raise_exception then
  if sqlerrm <> 'device_farm_mismatch' then raise; end if;
end $$;

do $$ begin
  perform public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333335',
    '11111111-1111-4111-8111-111111111111',
    '88888888-8888-4888-8888-888888888888', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  );
  raise exception 'inactive device telemetry was accepted';
exception when raise_exception then
  if sqlerrm <> 'inactive_device' then raise; end if;
end $$;

do $$ begin
  perform public.ingest_telemetry(
    '33333333-3333-4333-8333-333333333336',
    '11111111-1111-4111-8111-111111111111',
    '77777777-7777-4777-8777-777777777777', 1, 'temperature', 22.0,
    '°C', 'valid', '2026-09-23T12:00:00Z'
  );
  raise exception 'unknown device telemetry was accepted';
exception when raise_exception then
  if sqlerrm <> 'unknown_device' then raise; end if;
end $$;

do $$ begin
  if public.ingest_device_status(
    '44444444-4444-4444-8444-444444444444',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, true, false,
    'healthy', '2026-09-23T12:02:00Z', 120, '0.1.0', '{}'
  ) <> 'inserted' then
    raise exception 'device status was not inserted';
  end if;
  if public.ingest_device_status(
    '44444444-4444-4444-8444-444444444444',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222', 1, true, false,
    'healthy', '2026-09-23T12:02:00Z', 120, '0.1.0', '{}'
  ) <> 'duplicate' then
    raise exception 'device status redelivery was not idempotent';
  end if;
end $$;
reset role;

rollback;
