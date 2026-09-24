enum WeatherFreshness { fresh, stale, unavailable }

final class WeatherSnapshot {
  const WeatherSnapshot({
    required this.farmId,
    required this.sourceTime,
    required this.fetchedAt,
    required this.freshUntil,
    required this.staleUntil,
    required this.temperatureC,
    required this.relativeHumidityPercent,
    required this.currentPrecipitationMm,
    required this.currentIntervalSeconds,
    required this.weatherCode,
    required this.windSpeedKmh,
    required this.precipitationLast6hMm,
    required this.precipitationLast12hMm,
    required this.precipitationLast24hMm,
    required this.precipitationPrevious24hMm,
    required this.et0Last24hMm,
  });

  factory WeatherSnapshot.fromRow(
    Map<String, dynamic> row, {
    required String expectedFarmId,
  }) {
    final farmId = _string(row, 'farm_id');
    if (farmId != expectedFarmId) {
      throw const FormatException('Weather snapshot farm mismatch.');
    }
    final fetchedAt = _timestamp(row, 'fetched_at');
    final freshUntil = _timestamp(row, 'fresh_until');
    final staleUntil = _timestamp(row, 'stale_until');
    if (fetchedAt.isAfter(freshUntil) || !freshUntil.isBefore(staleUntil)) {
      throw const FormatException('Invalid weather freshness window.');
    }
    final humidity = _finiteNumber(row, 'relative_humidity_percent');
    final interval = _integer(row, 'current_interval_seconds');
    final precipitation = _finiteNumber(row, 'current_precipitation_mm');
    final wind = _finiteNumber(row, 'wind_speed_kmh');
    final precipitation6h = _finiteNumber(row, 'precipitation_last_6h_mm');
    final precipitation12h = _finiteNumber(row, 'precipitation_last_12h_mm');
    final precipitation24h = _finiteNumber(row, 'precipitation_last_24h_mm');
    final previous24h = _finiteNumber(row, 'precipitation_previous_24h_mm');
    final et0 = _finiteNumber(row, 'et0_last_24h_mm');
    if (humidity < 0 || humidity > 100 || interval <= 0) {
      throw const FormatException('Invalid weather measurement.');
    }
    for (final value in [
      precipitation,
      wind,
      precipitation6h,
      precipitation12h,
      precipitation24h,
      previous24h,
      et0,
    ]) {
      if (value < 0) {
        throw const FormatException(
          'Weather measurement must be non-negative.',
        );
      }
    }
    return WeatherSnapshot(
      farmId: farmId,
      sourceTime: _timestamp(row, 'source_time'),
      fetchedAt: fetchedAt,
      freshUntil: freshUntil,
      staleUntil: staleUntil,
      temperatureC: _finiteNumber(row, 'temperature_c'),
      relativeHumidityPercent: humidity,
      currentPrecipitationMm: precipitation,
      currentIntervalSeconds: interval,
      weatherCode: _integer(row, 'weather_code'),
      windSpeedKmh: wind,
      precipitationLast6hMm: precipitation6h,
      precipitationLast12hMm: precipitation12h,
      precipitationLast24hMm: precipitation24h,
      precipitationPrevious24hMm: previous24h,
      et0Last24hMm: et0,
    );
  }

  final String farmId;
  final DateTime sourceTime;
  final DateTime fetchedAt;
  final DateTime freshUntil;
  final DateTime staleUntil;
  final double temperatureC;
  final double relativeHumidityPercent;
  final double currentPrecipitationMm;
  final int currentIntervalSeconds;
  final int weatherCode;
  final double windSpeedKmh;
  final double precipitationLast6hMm;
  final double precipitationLast12hMm;
  final double precipitationLast24hMm;
  final double precipitationPrevious24hMm;
  final double et0Last24hMm;

  WeatherFreshness freshnessAt(DateTime now) {
    final utcNow = now.toUtc();
    if (!utcNow.isAfter(freshUntil)) return WeatherFreshness.fresh;
    if (!utcNow.isAfter(staleUntil)) return WeatherFreshness.stale;
    return WeatherFreshness.unavailable;
  }
}

String _string(Map<String, dynamic> row, String field) {
  final value = row[field];
  if (value is! String || value.isEmpty) {
    throw FormatException('$field must be a non-empty string.');
  }
  return value;
}

double _finiteNumber(Map<String, dynamic> row, String field) {
  final value = row[field];
  if (value is! num) throw FormatException('$field must be numeric.');
  final number = value.toDouble();
  if (!number.isFinite) throw FormatException('$field must be finite.');
  return number;
}

int _integer(Map<String, dynamic> row, String field) {
  final value = row[field];
  if (value is! int) throw FormatException('$field must be an integer.');
  return value;
}

DateTime _timestamp(Map<String, dynamic> row, String field) {
  final value = row[field];
  if (value is! String ||
      !RegExp(r'(?:[zZ]|[+-]\d{2}:\d{2})$').hasMatch(value)) {
    throw FormatException('$field must include a timezone.');
  }
  final timestamp = DateTime.tryParse(value);
  if (timestamp == null) throw FormatException('$field is invalid.');
  return timestamp.toUtc();
}
