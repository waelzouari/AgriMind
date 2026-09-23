enum AuthenticationFailureType { invalidCredentials, unavailable, unknown }

final class AuthenticationFailure implements Exception {
  const AuthenticationFailure(this.type);

  final AuthenticationFailureType type;

  String get userMessage => switch (type) {
    AuthenticationFailureType.invalidCredentials =>
      'Adresse e-mail ou mot de passe incorrect.',
    AuthenticationFailureType.unavailable =>
      'Le service d’authentification est temporairement indisponible.',
    AuthenticationFailureType.unknown =>
      'La connexion a échoué. Veuillez réessayer.',
  };
}
