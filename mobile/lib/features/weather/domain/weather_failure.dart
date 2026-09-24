enum WeatherFailureType { network, unauthorized, invalidSnapshot, unknown }

final class WeatherFailure implements Exception {
  const WeatherFailure(this.type);

  final WeatherFailureType type;

  String get userMessage => switch (type) {
    WeatherFailureType.network =>
      'La météo ne peut pas être actualisée sans connexion.',
    WeatherFailureType.unauthorized =>
      'Vous n’êtes pas autorisé à consulter cette météo.',
    WeatherFailureType.invalidSnapshot =>
      'Les données météo reçues sont invalides.',
    WeatherFailureType.unknown => 'La météo est momentanément indisponible.',
  };
}
