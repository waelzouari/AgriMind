import 'package:agrimind/features/weather/application/weather_repository.dart';
import 'package:agrimind/features/weather/domain/weather_failure.dart';
import 'package:agrimind/features/weather/domain/weather_snapshot.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

abstract interface class WeatherRowSource {
  Future<Map<String, dynamic>?> findForFarm(String farmId);
}

final class SupabaseWeatherRowSource implements WeatherRowSource {
  SupabaseWeatherRowSource(this._client);

  final SupabaseClient _client;

  @override
  Future<Map<String, dynamic>?> findForFarm(String farmId) => _client
      .from('weather_snapshots')
      .select(_weatherColumns)
      .eq('farm_id', farmId)
      .maybeSingle();
}

final class SupabaseWeatherRepository implements WeatherRepository {
  SupabaseWeatherRepository(this._source);

  final WeatherRowSource _source;

  @override
  Future<WeatherSnapshot?> findForFarm(String farmId) async {
    try {
      final row = await _source.findForFarm(farmId);
      return row == null
          ? null
          : WeatherSnapshot.fromRow(row, expectedFarmId: farmId);
    } on WeatherFailure {
      rethrow;
    } on PostgrestException catch (error) {
      throw mapWeatherPostgrestException(error);
    } on FormatException {
      throw const WeatherFailure(WeatherFailureType.invalidSnapshot);
    } on Object {
      throw const WeatherFailure(WeatherFailureType.unknown);
    }
  }
}

WeatherFailure mapWeatherPostgrestException(PostgrestException error) {
  if (error.code == '42501') {
    return const WeatherFailure(WeatherFailureType.unauthorized);
  }
  final code = error.code ?? '';
  if (code.startsWith('08') || code.startsWith('PGRST0')) {
    return const WeatherFailure(WeatherFailureType.network);
  }
  return const WeatherFailure(WeatherFailureType.unknown);
}

const _weatherColumns =
    'farm_id,source_time,fetched_at,'
    'fresh_until,stale_until,temperature_c,relative_humidity_percent,'
    'current_precipitation_mm,current_interval_seconds,weather_code,'
    'wind_speed_kmh,precipitation_last_6h_mm,precipitation_last_12h_mm,'
    'precipitation_last_24h_mm,precipitation_previous_24h_mm,et0_last_24h_mm';
