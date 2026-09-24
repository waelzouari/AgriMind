import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('accepts either no location or a valid coordinate pair', () {
    expect(Farm(id: 'a', name: 'A').hasLocation, isFalse);
    expect(
      Farm(id: 'a', name: 'A', latitude: -90, longitude: 180).hasLocation,
      isTrue,
    );
  });

  test('rejects partial, non-finite, and out-of-range locations', () {
    final invalidFactories = <Farm Function()>[
      () => Farm(id: 'a', name: 'A', latitude: 1),
      () => Farm(id: 'a', name: 'A', latitude: double.nan, longitude: 1),
      () => Farm(id: 'a', name: 'A', latitude: double.infinity, longitude: 1),
      () => Farm(
        id: 'a',
        name: 'A',
        latitude: 1,
        longitude: double.negativeInfinity,
      ),
      () => Farm(id: 'a', name: 'A', latitude: 91, longitude: 1),
      () => Farm(id: 'a', name: 'A', latitude: 1, longitude: -181),
    ];
    for (final create in invalidFactories) {
      expect(create, throwsArgumentError);
    }
  });
}
