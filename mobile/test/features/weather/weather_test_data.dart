import 'package:agrimind/features/weather/domain/weather_snapshot.dart';

Map<String, dynamic> weatherRow({
  String farmId = 'farm-a',
  String fetchedAt = '2026-09-24T10:00:00Z',
  String freshUntil = '2026-09-24T10:15:00Z',
  String staleUntil = '2026-09-24T11:00:00Z',
}) => {
  'farm_id': farmId,
  'source_time': '2026-09-24T09:45:00Z',
  'fetched_at': fetchedAt,
  'fresh_until': freshUntil,
  'stale_until': staleUntil,
  'temperature_c': 24.34,
  'relative_humidity_percent': 63.6,
  'current_precipitation_mm': 0.25,
  'current_interval_seconds': 900,
  'weather_code': 3,
  'wind_speed_kmh': 11.26,
  'precipitation_last_6h_mm': 1.0,
  'precipitation_last_12h_mm': 2.0,
  'precipitation_last_24h_mm': 3.45,
  'precipitation_previous_24h_mm': 4.0,
  'et0_last_24h_mm': 2.35,
};

WeatherSnapshot weatherSnapshot({
  String farmId = 'farm-a',
  String freshUntil = '2026-09-24T10:15:00Z',
  String staleUntil = '2026-09-24T11:00:00Z',
}) => WeatherSnapshot.fromRow(
  weatherRow(farmId: farmId, freshUntil: freshUntil, staleUntil: staleUntil),
  expectedFarmId: farmId,
);
