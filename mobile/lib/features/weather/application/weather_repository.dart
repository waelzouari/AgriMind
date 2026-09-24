import 'package:agrimind/features/weather/domain/weather_snapshot.dart';

abstract interface class WeatherRepository {
  Future<WeatherSnapshot?> findForFarm(String farmId);
}
