import 'package:agrimind/features/onboarding/domain/farm_failure.dart';
import 'package:agrimind/features/onboarding/infrastructure/supabase_farm_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

void main() {
  test('maps complete farm coordinates and preserves missing location', () {
    final located = mapFarmRow({
      'id': 'farm-a',
      'name': 'Ferme A',
      'latitude': 34.74,
      'longitude': 10.76,
    });
    final unlocated = mapFarmRow({
      'id': 'farm-b',
      'name': 'Ferme B',
      'latitude': null,
      'longitude': null,
    });

    expect(located.latitude, 34.74);
    expect(located.longitude, 10.76);
    expect(unlocated.hasLocation, isFalse);
  });

  test('rejects malformed persisted farm coordinates', () {
    expect(
      () => mapFarmRow({
        'id': 'farm-a',
        'name': 'Ferme A',
        'latitude': 34.74,
        'longitude': null,
      }),
      throwsFormatException,
    );
    expect(
      () => mapFarmRow({
        'id': 'farm-a',
        'name': 'Ferme A',
        'latitude': double.infinity,
        'longitude': 10.76,
      }),
      throwsFormatException,
    );
  });

  test('maps authorization, conflict, and service failures safely', () {
    const cases = {
      '42501': FarmFailureType.unauthorized,
      '23505': FarmFailureType.conflict,
      '08006': FarmFailureType.unavailable,
      'PGRST000': FarmFailureType.unavailable,
      'XX000': FarmFailureType.unknown,
    };

    for (final entry in cases.entries) {
      final failure = mapFarmPostgrestException(
        PostgrestException(message: 'provider detail', code: entry.key),
      );
      expect(failure.type, entry.value);
      expect(failure.userMessage, isNot(contains('provider detail')));
    }
  });
}
