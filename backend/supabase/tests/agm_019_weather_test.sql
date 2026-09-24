-- AGM-019 optional farm location, weather cache constraints, grants, and RLS.

insert into auth.users(id) values
  ('19191919-1919-4919-8919-191919191911'),
  ('19191919-1919-4919-8919-191919191912'),
  ('19191919-1919-4919-8919-191919191913');

insert into public.farms(id, name) values
  ('19191919-1919-4919-8919-191919191901', 'Located farm'),
  ('19191919-1919-4919-8919-191919191902', 'Other farm'),
  ('19191919-1919-4919-8919-191919191903', 'Nullable location');

insert into public.farm_memberships(farm_id, user_id, role) values
  ('19191919-1919-4919-8919-191919191901', '19191919-1919-4919-8919-191919191911', 'owner'),
  ('19191919-1919-4919-8919-191919191901', '19191919-1919-4919-8919-191919191912', 'member'),
  ('19191919-1919-4919-8919-191919191902', '19191919-1919-4919-8919-191919191913', 'owner');

do $$
begin
  if exists (
    select 1 from public.farms
    where id = '19191919-1919-4919-8919-191919191903'
      and (latitude is not null or longitude is not null)
  ) then
    raise exception 'existing farms must retain NULL/NULL location';
  end if;
end;
$$;

do $$
begin
  begin
    update public.farms set latitude = 1 where id = '19191919-1919-4919-8919-191919191903';
    raise exception 'latitude without longitude accepted';
  exception when check_violation then null;
  end;
  begin
    update public.farms set longitude = 1 where id = '19191919-1919-4919-8919-191919191903';
    raise exception 'longitude without latitude accepted';
  exception when check_violation then null;
  end;
  update public.farms set latitude = -90, longitude = -180
    where id = '19191919-1919-4919-8919-191919191903';
  update public.farms set latitude = 90, longitude = 180
    where id = '19191919-1919-4919-8919-191919191903';
  begin
    update public.farms set latitude = 90.01 where id = '19191919-1919-4919-8919-191919191903';
    raise exception 'out-of-range latitude accepted';
  exception when check_violation then null;
  end;
  begin
    update public.farms set longitude = 180.01 where id = '19191919-1919-4919-8919-191919191903';
    raise exception 'out-of-range longitude accepted';
  exception when check_violation then null;
  end;
  begin
    update public.farms set latitude = 'NaN'::double precision
    where id = '19191919-1919-4919-8919-191919191903';
    raise exception 'NaN latitude accepted';
  exception when check_violation then null;
  end;
  begin
    update public.farms set longitude = 'Infinity'::double precision
    where id = '19191919-1919-4919-8919-191919191903';
    raise exception 'Infinity longitude accepted';
  exception when check_violation then null;
  end;
  begin
    update public.farms set longitude = '-Infinity'::double precision
    where id = '19191919-1919-4919-8919-191919191903';
    raise exception '-Infinity longitude accepted';
  exception when check_violation then null;
  end;
end;
$$;

set role authenticated;
select set_config('request.jwt.claim.sub', '19191919-1919-4919-8919-191919191911', false);
update public.farms set latitude = 36.8065, longitude = 10.1815
where id = '19191919-1919-4919-8919-191919191901';

do $$
begin
  if not exists (
    select 1 from public.farms
    where id = '19191919-1919-4919-8919-191919191901'
      and latitude = 36.8065 and longitude = 10.1815
  ) then
    raise exception 'owner location update failed';
  end if;
end;
$$;

select set_config('request.jwt.claim.sub', '19191919-1919-4919-8919-191919191912', false);
update public.farms set latitude = 1, longitude = 1
where id = '19191919-1919-4919-8919-191919191901';

do $$
begin
  if exists (
    select 1 from public.farms
    where id = '19191919-1919-4919-8919-191919191901'
      and latitude = 1 and longitude = 1
  ) then
    raise exception 'member changed owner-only location';
  end if;
end;
$$;

reset role;
set role anon;
do $$
begin
  begin
    update public.farms set latitude = 2, longitude = 2
    where id = '19191919-1919-4919-8919-191919191901';
    raise exception 'anonymous location update accepted';
  exception when insufficient_privilege then null;
  end;
end;
$$;
reset role;

set role service_role;
insert into public.weather_snapshots(
  farm_id, provider, latitude, longitude, source_time, fetched_at,
  fresh_until, stale_until, temperature_c, relative_humidity_percent,
  current_precipitation_mm, current_interval_seconds, weather_code,
  wind_speed_kmh, precipitation_last_6h_mm, precipitation_last_12h_mm,
  precipitation_last_24h_mm, precipitation_previous_24h_mm, et0_last_24h_mm
) values
  ('19191919-1919-4919-8919-191919191901', 'open-meteo', 36.8065, 10.1815,
   '2026-09-23T12:00:00Z', '2026-09-23T12:05:00Z', '2026-09-23T12:35:00Z',
   '2026-09-23T18:05:00Z', 25, 60, 0, 900, 1, 10, 1, 2, 3, 4, 5),
  ('19191919-1919-4919-8919-191919191902', 'open-meteo', 35, 9,
   '2026-09-23T12:00:00Z', '2026-09-23T12:05:00Z', '2026-09-23T12:35:00Z',
   '2026-09-23T18:05:00Z', 24, 55, 0, 900, 2, 9, 1, 2, 3, 4, 5);
reset role;

set role authenticated;
select set_config('request.jwt.claim.sub', '19191919-1919-4919-8919-191919191912', false);
do $$
begin
  if (select count(*) from public.weather_snapshots) <> 1 then
    raise exception 'member weather isolation failed';
  end if;
  begin
    insert into public.weather_snapshots(
      farm_id, provider, latitude, longitude, source_time, fetched_at,
      fresh_until, stale_until, temperature_c, relative_humidity_percent,
      current_precipitation_mm, current_interval_seconds, weather_code,
      wind_speed_kmh, precipitation_last_6h_mm, precipitation_last_12h_mm,
      precipitation_last_24h_mm, precipitation_previous_24h_mm, et0_last_24h_mm
    ) values (
      '19191919-1919-4919-8919-191919191903', 'open-meteo', 0, 0, now(), now(),
      now() + interval '30 minutes', now() + interval '6 hours', 0, 0, 0, 900, 0,
      0, 0, 0, 0, 0, 0
    );
    raise exception 'authenticated insert accepted';
  exception when insufficient_privilege then null;
  end;
  begin
    update public.weather_snapshots set weather_code = 3;
    raise exception 'authenticated update accepted';
  exception when insufficient_privilege then null;
  end;
  begin
    delete from public.weather_snapshots;
    raise exception 'authenticated delete accepted';
  exception when insufficient_privilege then null;
  end;
end;
$$;
reset role;

set role anon;
do $$
begin
  begin
    perform count(*) from public.weather_snapshots;
    raise exception 'anonymous weather read accepted';
  exception when insufficient_privilege then null;
  end;
end;
$$;
reset role;

delete from public.farms where id = '19191919-1919-4919-8919-191919191902';
do $$
begin
  if exists (
    select 1 from public.weather_snapshots
    where farm_id = '19191919-1919-4919-8919-191919191902'
  ) then
    raise exception 'weather snapshot did not cascade with farm';
  end if;
end;
$$;
