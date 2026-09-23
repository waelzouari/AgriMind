-- AGM-010: relational MVP schema. RLS policies intentionally belong to AGM-011.

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create function public.valid_error_codes(value text[])
returns boolean
language sql
immutable
strict
set search_path = pg_catalog
as $$
  select cardinality(value) <= 16
    and not exists (
      select 1
      from unnest(value) as code
      where code is null
         or code !~ '^[a-z0-9]+(?:_[a-z0-9]+)*$'
         or length(code) > 64
    );
$$;

create table public.farms (
  id uuid primary key check (id <> '00000000-0000-0000-0000-000000000000'),
  name text not null check (btrim(name) <> ''),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.farm_memberships (
  farm_id uuid not null references public.farms(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'member')),
  created_at timestamptz not null default now(),
  primary key (farm_id, user_id)
);

create table public.devices (
  id uuid primary key check (id <> '00000000-0000-0000-0000-000000000000'),
  farm_id uuid not null references public.farms(id) on delete restrict,
  label text check (label is null or btrim(label) <> ''),
  is_active boolean not null default true,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, farm_id)
);

create table public.telemetry_readings (
  message_id uuid primary key check (
    message_id <> '00000000-0000-0000-0000-000000000000'
  ),
  farm_id uuid not null,
  device_id uuid not null,
  schema_version smallint not null check (schema_version = 1),
  metric text not null check (
    metric in ('soil_moisture', 'temperature', 'humidity', 'tank_level')
  ),
  value double precision not null check (
    value not in (
      'NaN'::double precision,
      'Infinity'::double precision,
      '-Infinity'::double precision
    )
  ),
  unit text not null,
  quality text not null check (quality in ('valid', 'estimated')),
  recorded_at timestamptz not null,
  ingested_at timestamptz not null default now(),
  foreign key (device_id, farm_id)
    references public.devices(id, farm_id) on delete restrict,
  check (
    (metric in ('soil_moisture', 'humidity') and unit = '%')
    or (metric = 'temperature' and unit = '°C')
    or (metric = 'tank_level' and unit = 'cm')
  )
);

create table public.device_status_events (
  message_id uuid primary key check (
    message_id <> '00000000-0000-0000-0000-000000000000'
  ),
  farm_id uuid not null,
  device_id uuid not null,
  schema_version smallint not null check (schema_version = 1),
  online boolean not null,
  pump_state boolean not null,
  health text not null check (health in ('healthy', 'degraded', 'fault')),
  recorded_at timestamptz not null,
  uptime_seconds bigint not null check (uptime_seconds >= 0),
  firmware_version text not null check (
    length(firmware_version) between 1 and 64
  ),
  errors text[] not null default '{}'::text[] check (
    public.valid_error_codes(errors)
  ),
  ingested_at timestamptz not null default now(),
  foreign key (device_id, farm_id)
    references public.devices(id, farm_id) on delete restrict
);

create table public.command_acknowledgements (
  acknowledgement_id uuid primary key check (
    acknowledgement_id <> '00000000-0000-0000-0000-000000000000'
  ),
  command_id uuid not null check (
    command_id <> '00000000-0000-0000-0000-000000000000'
  ),
  farm_id uuid not null,
  device_id uuid not null,
  schema_version smallint not null check (schema_version = 1),
  status text not null check (
    status in ('accepted', 'rejected', 'completed', 'failed')
  ),
  occurred_at timestamptz not null,
  reason_code text,
  pump_state boolean,
  ingested_at timestamptz not null default now(),
  foreign key (device_id, farm_id)
    references public.devices(id, farm_id) on delete restrict,
  check (
    (status in ('rejected', 'failed')
      and reason_code is not null
      and reason_code ~ '^[a-z0-9]+(?:_[a-z0-9]+)*$'
      and length(reason_code) <= 64)
    or (status in ('accepted', 'completed') and reason_code is null)
  )
);

create table public.irrigation_results (
  event_id uuid primary key check (
    event_id <> '00000000-0000-0000-0000-000000000000'
  ),
  farm_id uuid not null,
  device_id uuid not null,
  schema_version smallint not null check (schema_version = 1),
  soil_moisture_before numeric not null check (
    soil_moisture_before between 0 and 100
  ),
  soil_moisture_after numeric not null check (
    soil_moisture_after between 0 and 100
  ),
  delta numeric not null check (delta between -100 and 100),
  result text not null check (result in ('increased', 'unchanged', 'decreased')),
  completed_at timestamptz not null,
  ingested_at timestamptz not null default now(),
  foreign key (device_id, farm_id)
    references public.devices(id, farm_id) on delete restrict,
  check (delta = round(soil_moisture_after - soil_moisture_before, 1)),
  check (
    (delta > 0 and result = 'increased')
    or (delta = 0 and result = 'unchanged')
    or (delta < 0 and result = 'decreased')
  )
);

create index farm_memberships_user_farm_idx
  on public.farm_memberships(user_id, farm_id);
create index devices_farm_created_idx
  on public.devices(farm_id, created_at);
create index telemetry_farm_recorded_idx
  on public.telemetry_readings(farm_id, recorded_at desc);
create index telemetry_device_recorded_idx
  on public.telemetry_readings(device_id, recorded_at desc);
create index device_status_farm_recorded_idx
  on public.device_status_events(farm_id, recorded_at desc);
create index device_status_device_recorded_idx
  on public.device_status_events(device_id, recorded_at desc);
create index acknowledgements_farm_occurred_idx
  on public.command_acknowledgements(farm_id, occurred_at desc);
create index acknowledgements_device_occurred_idx
  on public.command_acknowledgements(device_id, occurred_at desc);
create index acknowledgements_command_occurred_idx
  on public.command_acknowledgements(command_id, occurred_at desc);
create index irrigation_results_farm_completed_idx
  on public.irrigation_results(farm_id, completed_at desc);
create index irrigation_results_device_completed_idx
  on public.irrigation_results(device_id, completed_at desc);

create trigger farms_set_updated_at
before update on public.farms
for each row execute function public.set_updated_at();

create trigger devices_set_updated_at
before update on public.devices
for each row execute function public.set_updated_at();

comment on table public.farm_memberships is
  'Membership relation prepared for AGM-011 RLS; no RLS policy is defined by AGM-010.';
comment on table public.telemetry_readings is
  'Canonical v1 telemetry; message_id provides at-least-once ingestion deduplication.';
comment on table public.command_acknowledgements is
  'Canonical v1 acknowledgements; this table does not authorize or execute commands.';
