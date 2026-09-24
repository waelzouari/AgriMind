-- AGM-019 MVP provisional implementation policy -- subject to later team review.
-- Adds optional farm coordinates and a server-written current weather cache.

alter table public.farms
  add column latitude double precision,
  add column longitude double precision,
  add constraint farms_location_pair_check check (
    (latitude is null and longitude is null)
    or (latitude is not null and longitude is not null)
  ),
  add constraint farms_latitude_check check (
    latitude is null or (
      latitude between -90 and 90
      and latitude not in ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
    )
  ),
  add constraint farms_longitude_check check (
    longitude is null or (
      longitude between -180 and 180
      and longitude not in ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
    )
  );

grant update (latitude, longitude) on table public.farms to authenticated;

create table public.weather_snapshots (
  farm_id uuid primary key references public.farms(id) on delete cascade,
  provider text not null check (provider = 'open-meteo'),
  latitude double precision not null check (
    latitude between -90 and 90
    and latitude not in ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
  ),
  longitude double precision not null check (
    longitude between -180 and 180
    and longitude not in ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
  ),
  source_time timestamptz not null,
  fetched_at timestamptz not null,
  fresh_until timestamptz not null,
  stale_until timestamptz not null,
  temperature_c double precision not null check (
    temperature_c not in ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
  ),
  relative_humidity_percent double precision not null check (
    relative_humidity_percent between 0 and 100
    and relative_humidity_percent not in ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
  ),
  current_precipitation_mm double precision not null check (
    current_precipitation_mm >= 0
    and current_precipitation_mm not in ('NaN'::double precision, 'Infinity'::double precision)
  ),
  current_interval_seconds integer not null check (current_interval_seconds > 0),
  weather_code integer not null,
  wind_speed_kmh double precision not null check (
    wind_speed_kmh >= 0
    and wind_speed_kmh not in ('NaN'::double precision, 'Infinity'::double precision)
  ),
  precipitation_last_6h_mm double precision not null check (
    precipitation_last_6h_mm >= 0
    and precipitation_last_6h_mm not in ('NaN'::double precision, 'Infinity'::double precision)
  ),
  precipitation_last_12h_mm double precision not null check (
    precipitation_last_12h_mm >= 0
    and precipitation_last_12h_mm not in ('NaN'::double precision, 'Infinity'::double precision)
  ),
  precipitation_last_24h_mm double precision not null check (
    precipitation_last_24h_mm >= 0
    and precipitation_last_24h_mm not in ('NaN'::double precision, 'Infinity'::double precision)
  ),
  precipitation_previous_24h_mm double precision not null check (
    precipitation_previous_24h_mm >= 0
    and precipitation_previous_24h_mm not in ('NaN'::double precision, 'Infinity'::double precision)
  ),
  et0_last_24h_mm double precision not null check (
    et0_last_24h_mm >= 0
    and et0_last_24h_mm not in ('NaN'::double precision, 'Infinity'::double precision)
  ),
  updated_at timestamptz not null default now(),
  check (fetched_at <= fresh_until and fresh_until < stale_until)
);

create trigger weather_snapshots_set_updated_at
before update on public.weather_snapshots
for each row execute function public.set_updated_at();

alter table public.weather_snapshots enable row level security;

revoke all on table public.weather_snapshots from public, anon, authenticated;
grant select on table public.weather_snapshots to authenticated;
grant all on table public.weather_snapshots to service_role;

create policy weather_snapshots_select_member
on public.weather_snapshots for select to authenticated
using (private.is_farm_member(farm_id));

comment on table public.weather_snapshots is
  'Current farm weather cache; server-written and member-readable for AGM-019.';
comment on column public.weather_snapshots.current_precipitation_mm is
  'Open-Meteo current precipitation over current_interval_seconds, in millimetres.';
