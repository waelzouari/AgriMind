import 'dart:async';

import 'package:agrimind/features/weather/application/weather_repository.dart';
import 'package:agrimind/features/weather/domain/weather_snapshot.dart';

final class FakeWeatherRepository implements WeatherRepository {
  WeatherSnapshot? result;
  Object? error;
  Completer<WeatherSnapshot?>? completer;
  int calls = 0;
  String? requestedFarmId;

  @override
  Future<WeatherSnapshot?> findForFarm(String farmId) async {
    calls++;
    requestedFarmId = farmId;
    if (error case final failure?) throw failure;
    return completer?.future ?? result;
  }
}
