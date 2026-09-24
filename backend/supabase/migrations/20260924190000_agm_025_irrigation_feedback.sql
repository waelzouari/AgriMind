-- AGM-025: trusted idempotent ingestion for technical ACK lifecycle and
-- measured agronomic irrigation results. Existing client RLS remains unchanged.

create function public.ingest_command_acknowledgement(
  incoming_acknowledgement_id uuid,
  incoming_command_id uuid,
  incoming_farm_id uuid,
  incoming_device_id uuid,
  incoming_schema_version integer,
  incoming_status text,
  incoming_occurred_at timestamptz,
  incoming_reason_code text,
  incoming_pump_state boolean
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  registered_farm_id uuid;
  device_active boolean;
  inserted_rows integer;
  existing public.command_acknowledgements%rowtype;
begin
  select device.farm_id, device.is_active
    into registered_farm_id, device_active
  from public.devices as device
  where device.id = incoming_device_id
  for update;

  if not found then
    raise exception using errcode = 'P0001', message = 'unknown_device';
  end if;
  if not device_active then
    raise exception using errcode = 'P0001', message = 'inactive_device';
  end if;
  if registered_farm_id <> incoming_farm_id then
    raise exception using errcode = 'P0001', message = 'device_farm_mismatch';
  end if;

  insert into public.command_acknowledgements(
    acknowledgement_id, command_id, farm_id, device_id, schema_version,
    status, occurred_at, reason_code, pump_state
  ) values (
    incoming_acknowledgement_id, incoming_command_id, registered_farm_id,
    incoming_device_id, incoming_schema_version, incoming_status,
    incoming_occurred_at, incoming_reason_code, incoming_pump_state
  ) on conflict (acknowledgement_id) do nothing;
  get diagnostics inserted_rows = row_count;

  if inserted_rows = 1 then
    update public.devices set last_seen_at = now() where id = incoming_device_id;
    return 'inserted';
  end if;

  select * into existing
  from public.command_acknowledgements
  where acknowledgement_id = incoming_acknowledgement_id;

  if existing.command_id = incoming_command_id
     and existing.farm_id = registered_farm_id
     and existing.device_id = incoming_device_id
     and existing.schema_version = incoming_schema_version
     and existing.status = incoming_status
     and existing.occurred_at = incoming_occurred_at
     and existing.reason_code is not distinct from incoming_reason_code
     and existing.pump_state is not distinct from incoming_pump_state then
    return 'duplicate';
  end if;

  raise exception using errcode = 'P0001', message = 'message_id_conflict';
end;
$$;

create function public.ingest_irrigation_result(
  incoming_event_id uuid,
  incoming_farm_id uuid,
  incoming_device_id uuid,
  incoming_schema_version integer,
  incoming_soil_moisture_before numeric,
  incoming_soil_moisture_after numeric,
  incoming_delta numeric,
  incoming_result text,
  incoming_completed_at timestamptz
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  registered_farm_id uuid;
  device_active boolean;
  inserted_rows integer;
  existing public.irrigation_results%rowtype;
begin
  select device.farm_id, device.is_active
    into registered_farm_id, device_active
  from public.devices as device
  where device.id = incoming_device_id
  for update;

  if not found then
    raise exception using errcode = 'P0001', message = 'unknown_device';
  end if;
  if not device_active then
    raise exception using errcode = 'P0001', message = 'inactive_device';
  end if;
  if registered_farm_id <> incoming_farm_id then
    raise exception using errcode = 'P0001', message = 'device_farm_mismatch';
  end if;

  insert into public.irrigation_results(
    event_id, farm_id, device_id, schema_version, soil_moisture_before,
    soil_moisture_after, delta, result, completed_at
  ) values (
    incoming_event_id, registered_farm_id, incoming_device_id,
    incoming_schema_version, incoming_soil_moisture_before,
    incoming_soil_moisture_after, incoming_delta, incoming_result,
    incoming_completed_at
  ) on conflict (event_id) do nothing;
  get diagnostics inserted_rows = row_count;

  if inserted_rows = 1 then
    update public.devices set last_seen_at = now() where id = incoming_device_id;
    return 'inserted';
  end if;

  select * into existing
  from public.irrigation_results
  where event_id = incoming_event_id;

  if existing.farm_id = registered_farm_id
     and existing.device_id = incoming_device_id
     and existing.schema_version = incoming_schema_version
     and existing.soil_moisture_before = incoming_soil_moisture_before
     and existing.soil_moisture_after = incoming_soil_moisture_after
     and existing.delta = incoming_delta
     and existing.result = incoming_result
     and existing.completed_at = incoming_completed_at then
    return 'duplicate';
  end if;

  raise exception using errcode = 'P0001', message = 'message_id_conflict';
end;
$$;

revoke all on function public.ingest_command_acknowledgement(
  uuid, uuid, uuid, uuid, integer, text, timestamptz, text, boolean
) from public, anon, authenticated;
revoke all on function public.ingest_irrigation_result(
  uuid, uuid, uuid, integer, numeric, numeric, numeric, text, timestamptz
) from public, anon, authenticated;

grant execute on function public.ingest_command_acknowledgement(
  uuid, uuid, uuid, uuid, integer, text, timestamptz, text, boolean
) to service_role;
grant execute on function public.ingest_irrigation_result(
  uuid, uuid, uuid, integer, numeric, numeric, numeric, text, timestamptz
) to service_role;

comment on function public.ingest_command_acknowledgement(
  uuid, uuid, uuid, uuid, integer, text, timestamptz, text, boolean
) is 'Trusted AGM-025 technical lifecycle ingestion; derives farm authority from devices.';
comment on function public.ingest_irrigation_result(
  uuid, uuid, uuid, integer, numeric, numeric, numeric, text, timestamptz
) is 'Trusted AGM-025 measured agronomic result ingestion; derives farm authority from devices.';
