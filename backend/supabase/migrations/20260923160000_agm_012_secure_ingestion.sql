-- AGM-012: atomic trusted ingestion. Client RLS policies remain unchanged.

create function public.ingest_telemetry(
  incoming_message_id uuid,
  incoming_farm_id uuid,
  incoming_device_id uuid,
  incoming_schema_version integer,
  incoming_metric text,
  incoming_value double precision,
  incoming_unit text,
  incoming_quality text,
  incoming_recorded_at timestamptz
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
  existing public.telemetry_readings%rowtype;
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

  insert into public.telemetry_readings(
    message_id, farm_id, device_id, schema_version, metric, value, unit,
    quality, recorded_at
  ) values (
    incoming_message_id, registered_farm_id, incoming_device_id,
    incoming_schema_version, incoming_metric, incoming_value, incoming_unit,
    incoming_quality, incoming_recorded_at
  ) on conflict (message_id) do nothing;
  get diagnostics inserted_rows = row_count;

  if inserted_rows = 1 then
    update public.devices
    set last_seen_at = now()
    where id = incoming_device_id;
    return 'inserted';
  end if;

  select * into existing
  from public.telemetry_readings
  where message_id = incoming_message_id;

  if existing.farm_id = registered_farm_id
     and existing.device_id = incoming_device_id
     and existing.schema_version = incoming_schema_version
     and existing.metric = incoming_metric
     and existing.value = incoming_value
     and existing.unit = incoming_unit
     and existing.quality = incoming_quality
     and existing.recorded_at = incoming_recorded_at then
    return 'duplicate';
  end if;

  raise exception using errcode = 'P0001', message = 'message_id_conflict';
end;
$$;

create function public.ingest_device_status(
  incoming_message_id uuid,
  incoming_farm_id uuid,
  incoming_device_id uuid,
  incoming_schema_version integer,
  incoming_online boolean,
  incoming_pump_state boolean,
  incoming_health text,
  incoming_recorded_at timestamptz,
  incoming_uptime_seconds bigint,
  incoming_firmware_version text,
  incoming_errors text[]
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
  existing public.device_status_events%rowtype;
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

  insert into public.device_status_events(
    message_id, farm_id, device_id, schema_version, online, pump_state,
    health, recorded_at, uptime_seconds, firmware_version, errors
  ) values (
    incoming_message_id, registered_farm_id, incoming_device_id,
    incoming_schema_version, incoming_online, incoming_pump_state,
    incoming_health, incoming_recorded_at, incoming_uptime_seconds,
    incoming_firmware_version, incoming_errors
  ) on conflict (message_id) do nothing;
  get diagnostics inserted_rows = row_count;

  if inserted_rows = 1 then
    update public.devices
    set last_seen_at = now()
    where id = incoming_device_id;
    return 'inserted';
  end if;

  select * into existing
  from public.device_status_events
  where message_id = incoming_message_id;

  if existing.farm_id = registered_farm_id
     and existing.device_id = incoming_device_id
     and existing.schema_version = incoming_schema_version
     and existing.online = incoming_online
     and existing.pump_state = incoming_pump_state
     and existing.health = incoming_health
     and existing.recorded_at = incoming_recorded_at
     and existing.uptime_seconds = incoming_uptime_seconds
     and existing.firmware_version = incoming_firmware_version
     and existing.errors = incoming_errors then
    return 'duplicate';
  end if;

  raise exception using errcode = 'P0001', message = 'message_id_conflict';
end;
$$;

revoke all on function public.ingest_telemetry(
  uuid, uuid, uuid, integer, text, double precision, text, text, timestamptz
) from public, anon, authenticated;
revoke all on function public.ingest_device_status(
  uuid, uuid, uuid, integer, boolean, boolean, text, timestamptz, bigint,
  text, text[]
) from public, anon, authenticated;

grant execute on function public.ingest_telemetry(
  uuid, uuid, uuid, integer, text, double precision, text, text, timestamptz
) to service_role;
grant execute on function public.ingest_device_status(
  uuid, uuid, uuid, integer, boolean, boolean, text, timestamptz, bigint,
  text, text[]
) to service_role;

comment on function public.ingest_telemetry(
  uuid, uuid, uuid, integer, text, double precision, text, text, timestamptz
) is 'Trusted AGM-012 telemetry ingestion; derives farm authority from devices.';
comment on function public.ingest_device_status(
  uuid, uuid, uuid, integer, boolean, boolean, text, timestamptz, bigint,
  text, text[]
) is 'Trusted AGM-012 status ingestion; derives farm authority from devices.';
