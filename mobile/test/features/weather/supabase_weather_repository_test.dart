import 'package:agrimind/features/weather/domain/weather_failure.dart';
import 'package:agrimind/features/weather/infrastructure/supabase_weather_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'weather_test_data.dart';

final class _RowSource implements WeatherRowSource {
  Map<String, dynamic>? row;
  Object? error;
  String? farmId;

  @override
  Future<Map<String, dynamic>?> findForFarm(String farmId) async {
    this.farmId = farmId;
    if (error case final failure?) throw failure;
    return row;
  }
}

void main() {
  test('requests the selected farm and maps one row', () async {
    final source = _RowSource()..row = weatherRow();
    final result = await SupabaseWeatherRepository(
      source,
    ).findForFarm('farm-a');

    expect(source.farmId, 'farm-a');
    expect(result?.farmId, 'farm-a');
  });

  test('returns null when no snapshot exists', () async {
    final result = await SupabaseWeatherRepository(
      _RowSource(),
    ).findForFarm('farm-a');
    expect(result, isNull);
  });

  test(
    'maps invalid rows and provider failures to safe typed failures',
    () async {
      final invalid = _RowSource()
        ..row = {...weatherRow(), 'relative_humidity_percent': 200};
      await expectLater(
        SupabaseWeatherRepository(invalid).findForFarm('farm-a'),
        throwsA(
          isA<WeatherFailure>().having(
            (failure) => failure.type,
            'type',
            WeatherFailureType.invalidSnapshot,
          ),
        ),
      );

      const cases = {
        '42501': WeatherFailureType.unauthorized,
        '08006': WeatherFailureType.network,
        'PGRST000': WeatherFailureType.network,
        'XX000': WeatherFailureType.unknown,
      };
      for (final entry in cases.entries) {
        final failure = mapWeatherPostgrestException(
          PostgrestException(message: 'provider detail', code: entry.key),
        );
        expect(failure.type, entry.value);
        expect(failure.userMessage, isNot(contains('provider detail')));
      }
    },
  );
}
