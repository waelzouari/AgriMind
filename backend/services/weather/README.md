# Weather aggregation service

AGM-019 fetches farm-local weather from the public Open-Meteo Forecast API,
computes rolling precipitation and ET0 aggregates, and stores one current
snapshot per farm in PostgreSQL. It is an informative cloud capability only:
it publishes no MQTT command, controls no pump or GPIO, and cannot bypass the
Raspberry Pi safety gate. AGM-020 owns the Flutter weather repository and UI.

## AGM-019 MVP provisional implementation policy

These values are implementation defaults for the TecWeek MVP and are subject
to architecture/product review:

- farm coordinates are nullable and owners may update latitude/longitude;
- internal and persisted timestamps use UTC;
- temperature uses Celsius, precipitation and ET0 use millimetres, and wind
  uses km/h;
- fresh lifetime is 30 minutes;
- stale data remain usable through 6 hours, with an explicit stale result;
- the refresh loop runs every 15 minutes;
- Open-Meteo Forecast API provides current conditions and hourly precipitation
  plus hourly `et0_fao_evapotranspiration`;
- PostgreSQL stores one persistent `weather_snapshots` row per farm;
- precipitation windows are rolling 6/12/24 hours plus the previous 24 hours;
- ET0 is the rolling sum of the last 24 complete hourly buckets.

All durations and the provider URL are configuration, not domain constants.

## Runtime

Install the independently deployed package and run it with a protected file:

```bash
python -m pip install -e "./backend/services/weather"
agrimind-weather --env-file /secure/path/weather.env
```

The service validates configuration, performs an immediate pass over farms,
and then waits for the configured interval. One farm failure does not stop
other farms. A missing location is a valid farm state: it is logged safely and
skipped without calling Open-Meteo.

The service-role key is a trusted backend secret. It must never be copied into
Flutter, edge configuration, logs, screenshots, fixtures, or Git. Open-Meteo's
public endpoint used here requires no API key.

## Cache and freshness

For unchanged coordinates, a fresh cache is returned without network access.
A stale cache triggers one provider attempt and is returned as stale only if
that attempt fails. Expired data are unavailable after a failed refresh. A
coordinate change invalidates the old snapshot even when it would otherwise be
fresh; weather from the previous location is never used as fallback.

`fresh_until` and `stale_until` are persisted rather than an `is_stale` flag.
Consumers derive state at read time:

- `now <= fresh_until`: fresh;
- `fresh_until < now <= stale_until`: stale but usable;
- `now > stale_until`: unavailable/expired.

## Snapshot contract for AGM-020

`public.weather_snapshots` is member-readable through RLS and directly writable
only by `service_role`. It contains source/fetch/freshness timestamps, the farm
coordinates used for the fetch, current conditions, and the rolling aggregates.
`current_precipitation_mm` covers `current_interval_seconds`; it must not be
presented as an hourly amount. AGM-020 remains responsible for user-facing
formatting and explicit fresh/stale/offline presentation.

## Testing boundary

Ordinary tests use an injectable HTTP transport and never contact Open-Meteo.
SQL tests validate the actual migration, grants, owner coordinate updates, RLS,
cross-farm isolation, service writes, and cascade behavior in disposable
PostgreSQL databases. No live Open-Meteo result is claimed by AGM-019 tests.
