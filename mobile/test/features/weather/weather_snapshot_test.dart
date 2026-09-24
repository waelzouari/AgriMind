import 'package:agrimind/features/weather/domain/weather_snapshot.dart';
import 'package:flutter_test/flutter_test.dart';

import 'weather_test_data.dart';

void main() {
  test(
    'parses the complete persisted snapshot without dropping aggregates',
    () {
      final snapshot = WeatherSnapshot.fromRow(
        weatherRow(),
        expectedFarmId: 'farm-a',
      );

      expect(snapshot.precipitationLast6hMm, 1);
      expect(snapshot.precipitationLast12hMm, 2);
      expect(snapshot.precipitationPrevious24hMm, 4);
      expect(snapshot.weatherCode, 3);
      expect(snapshot.fetchedAt.isUtc, isTrue);
    },
  );

  test('uses inclusive fresh and stale boundaries', () {
    final snapshot = weatherSnapshot();

    expect(
      snapshot.freshnessAt(DateTime.parse('2026-09-24T10:14:59Z')),
      WeatherFreshness.fresh,
    );
    expect(
      snapshot.freshnessAt(DateTime.parse('2026-09-24T10:15:00Z')),
      WeatherFreshness.fresh,
    );
    expect(
      snapshot.freshnessAt(DateTime.parse('2026-09-24T10:15:00.001Z')),
      WeatherFreshness.stale,
    );
    expect(
      snapshot.freshnessAt(DateTime.parse('2026-09-24T10:30:00Z')),
      WeatherFreshness.stale,
    );
    expect(
      snapshot.freshnessAt(DateTime.parse('2026-09-24T11:00:00Z')),
      WeatherFreshness.stale,
    );
    expect(
      snapshot.freshnessAt(DateTime.parse('2026-09-24T11:00:00.001Z')),
      WeatherFreshness.unavailable,
    );
  });

  test('rejects malformed, non-finite, mismatched, and naive data', () {
    final invalidRows = <Map<String, dynamic>>[
      {...weatherRow()}..remove('temperature_c'),
      {...weatherRow(), 'temperature_c': null},
      {...weatherRow(), 'temperature_c': '24'},
      {...weatherRow(), 'temperature_c': true},
      {...weatherRow(), 'farm_id': 'farm-b'},
      {...weatherRow(), 'temperature_c': double.nan},
      {...weatherRow(), 'wind_speed_kmh': double.infinity},
      {...weatherRow(), 'relative_humidity_percent': 101},
      {...weatherRow(), 'current_interval_seconds': 0},
      {...weatherRow(), 'current_interval_seconds': 15.0},
      {...weatherRow(), 'current_precipitation_mm': -1},
      {...weatherRow(), 'precipitation_last_24h_mm': -1},
      {...weatherRow(), 'wind_speed_kmh': -1},
      {...weatherRow(), 'et0_last_24h_mm': -1},
      {...weatherRow(), 'source_time': '2026-09-24T09:45:00'},
      {...weatherRow(), 'fetched_at': 'not-a-dateZ'},
      {
        ...weatherRow(),
        'fetched_at': '2026-09-24T10:16:00Z',
        'fresh_until': '2026-09-24T10:15:00Z',
      },
      {
        ...weatherRow(),
        'fresh_until': '2026-09-24T11:00:00Z',
        'stale_until': '2026-09-24T11:00:00Z',
      },
    ];

    for (final row in invalidRows) {
      expect(
        () => WeatherSnapshot.fromRow(row, expectedFarmId: 'farm-a'),
        throwsFormatException,
      );
    }
  });
}
