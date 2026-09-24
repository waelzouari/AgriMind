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
    from pg_proc where oid = 'public.ingest_command_acknowledgement(uuid,uuid,uuid,uuid,integer,text,timestamptz,text,boolean)'::regprocedure
  ) then
    raise exception 'acknowledgement RPC security configuration is invalid';
  end if;
  if has_function_privilege('anon', 'public.ingest_command_acknowledgement(uuid,uuid,uuid,uuid,integer,text,timestamptz,text,boolean)', 'EXECUTE')
     or has_function_privilege('authenticated', 'public.ingest_irrigation_result(uuid,uuid,uuid,integer,numeric,numeric,numeric,text,timestamptz)', 'EXECUTE')
     or not has_function_privilege('service_role', 'public.ingest_irrigation_result(uuid,uuid,uuid,integer,numeric,numeric,numeric,text,timestamptz)', 'EXECUTE') then
    raise exception 'AGM-025 RPC privileges are invalid';
  end if;
end $$;

set local role anon;
do $$ begin
  perform public.ingest_command_acknowledgement(
    '33333333-3333-4333-8333-333333333333',
    '44444444-4444-4444-8444-444444444444',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'completed', '2026-09-24T12:00:00Z', null, false
  );
  raise exception 'anon executed AGM-025 RPC';
exception when insufficient_privilege then null; end $$;
reset role;

set local role service_role;
do $$ begin
  if public.ingest_command_acknowledgement(
    '33333333-3333-4333-8333-333333333333',
    '44444444-4444-4444-8444-444444444444',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'completed', '2026-09-24T12:00:00Z', null, false
  ) <> 'inserted' then raise exception 'acknowledgement not inserted'; end if;
  if public.ingest_command_acknowledgement(
    '33333333-3333-4333-8333-333333333333',
    '44444444-4444-4444-8444-444444444444',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 'completed', '2026-09-24T12:00:00Z', null, false
  ) <> 'duplicate' then raise exception 'acknowledgement duplicate not idempotent'; end if;

  if public.ingest_irrigation_result(
    '55555555-5555-4555-8555-555555555555',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 40, 45, 5, 'increased', '2026-09-24T12:05:00Z'
  ) <> 'inserted' then raise exception 'irrigation result not inserted'; end if;
  if public.ingest_irrigation_result(
    '55555555-5555-4555-8555-555555555555',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 40, 45, 5, 'increased', '2026-09-24T12:05:00Z'
  ) <> 'duplicate' then raise exception 'irrigation result duplicate not idempotent'; end if;
end $$;

do $$ begin
  perform public.ingest_irrigation_result(
    '55555555-5555-4555-8555-555555555555',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    1, 40, 46, 6, 'increased', '2026-09-24T12:05:00Z'
  );
  raise exception 'conflicting result duplicate accepted';
exception when raise_exception then
  if sqlerrm <> 'message_id_conflict' then raise; end if;
end $$;

do $$ begin
  perform public.ingest_command_acknowledgement(
    '33333333-3333-4333-8333-333333333334',
    '44444444-4444-4444-8444-444444444445',
    '99999999-9999-4999-8999-999999999999',
    '22222222-2222-4222-8222-222222222222',
    1, 'completed', '2026-09-24T12:00:00Z', null, false
  );
  raise exception 'cross-farm acknowledgement accepted';
exception when raise_exception then
  if sqlerrm <> 'device_farm_mismatch' then raise; end if;
end $$;

do $$ begin
  perform public.ingest_irrigation_result(
    '55555555-5555-4555-8555-555555555556',
    '11111111-1111-4111-8111-111111111111',
    '88888888-8888-4888-8888-888888888888',
    1, 40, 45, 5, 'increased', '2026-09-24T12:05:00Z'
  );
  raise exception 'inactive device result accepted';
exception when raise_exception then
  if sqlerrm <> 'inactive_device' then raise; end if;
end $$;
reset role;

set local role authenticated;
select set_config('request.jwt.claim.sub', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
do $$ begin
  if (select count(*) from public.command_acknowledgements) <> 1
     or (select count(*) from public.irrigation_results) <> 1 then
    raise exception 'farm owner cannot read AGM-025 rows';
  end if;
end $$;
reset role;

rollback;
