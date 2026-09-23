enum FarmFailureType { unauthorized, unavailable, conflict, unknown }

final class FarmFailure implements Exception {
  const FarmFailure(this.type);

  final FarmFailureType type;

  String get userMessage => switch (type) {
    FarmFailureType.unauthorized =>
      'Votre session ne permet pas de configurer cette ferme.',
    FarmFailureType.unavailable =>
      'Le service est temporairement indisponible. Veuillez réessayer.',
    FarmFailureType.conflict =>
      'Une ferme est peut-être déjà configurée. Vérifiez à nouveau.',
    FarmFailureType.unknown =>
      'La configuration de la ferme a échoué. Veuillez réessayer.',
  };
}
