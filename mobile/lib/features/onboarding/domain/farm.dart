final class Farm {
  factory Farm({
    required String id,
    required String name,
    double? latitude,
    double? longitude,
  }) {
    if ((latitude == null) != (longitude == null)) {
      throw ArgumentError('Farm coordinates must be paired.');
    }
    if (latitude != null &&
        (!latitude.isFinite || latitude < -90 || latitude > 90)) {
      throw ArgumentError.value(latitude, 'latitude');
    }
    if (longitude != null &&
        (!longitude.isFinite || longitude < -180 || longitude > 180)) {
      throw ArgumentError.value(longitude, 'longitude');
    }
    return Farm._(id: id, name: name, latitude: latitude, longitude: longitude);
  }

  const Farm._({
    required this.id,
    required this.name,
    required this.latitude,
    required this.longitude,
  });

  final String id;
  final String name;
  final double? latitude;
  final double? longitude;

  bool get hasLocation => latitude != null && longitude != null;
}
