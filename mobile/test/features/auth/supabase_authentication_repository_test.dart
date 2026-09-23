import 'package:agrimind/features/auth/domain/authentication_failure.dart';
import 'package:agrimind/features/auth/infrastructure/supabase_authentication_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

void main() {
  test('maps only known credential rejection codes to invalid credentials', () {
    const rejectedCodes = ['invalid_credentials', 'user_not_found'];

    for (final code in rejectedCodes) {
      final failure = mapSupabaseAuthException(
        AuthApiException('provider detail', statusCode: '400', code: code),
      );
      expect(failure.type, AuthenticationFailureType.invalidCredentials);
    }
  });

  test('maps an unconfirmed email to a safe actionable failure', () {
    const exception = AuthApiException(
      'provider detail',
      statusCode: '400',
      code: 'email_not_confirmed',
    );

    final failure = mapSupabaseAuthException(exception);

    expect(failure.type, AuthenticationFailureType.emailNotConfirmed);
    expect(failure.userMessage, contains('Confirmez'));
    expect(failure.userMessage, isNot(contains(exception.message)));
  });

  test('maps retryable, rate-limit, and server failures to unavailable', () {
    final exceptions = <AuthException>[
      AuthRetryableFetchException(message: 'network detail'),
      const AuthApiException('rate limit detail', statusCode: '429'),
      const AuthApiException('server detail', statusCode: '503'),
    ];

    for (final exception in exceptions) {
      final failure = mapSupabaseAuthException(exception);
      expect(failure.type, AuthenticationFailureType.unavailable);
      expect(failure.userMessage, isNot(contains(exception.message)));
    }
  });

  test('maps unclassified provider failures to a safe unknown failure', () {
    const exception = AuthApiException(
      'configuration detail',
      statusCode: '401',
      code: 'unexpected_failure',
    );

    final failure = mapSupabaseAuthException(exception);

    expect(failure.type, AuthenticationFailureType.unknown);
    expect(failure.userMessage, isNot(contains(exception.message)));
  });
}
