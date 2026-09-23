import 'dart:async';

import 'package:agrimind/features/auth/application/authentication_repository.dart';
import 'package:agrimind/features/auth/domain/auth_session.dart' as domain;
import 'package:agrimind/features/auth/domain/authentication_failure.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

final class SupabaseAuthenticationRepository
    implements AuthenticationRepository {
  SupabaseAuthenticationRepository(this._client);

  final SupabaseClient _client;

  @override
  Stream<domain.AuthSession?> get authStateChanges =>
      _client.auth.onAuthStateChange.map((event) => _mapSession(event.session));

  @override
  Future<domain.AuthSession?> restoreSession() async =>
      _mapSession(_client.auth.currentSession);

  @override
  Future<domain.AuthSession> signIn({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _client.auth.signInWithPassword(
        email: email,
        password: password,
      );
      final session = _mapSession(response.session);
      if (session == null) {
        throw const AuthenticationFailure(
          AuthenticationFailureType.invalidCredentials,
        );
      }
      return session;
    } on AuthException catch (error) {
      throw mapSupabaseAuthException(error);
    } on AuthenticationFailure {
      rethrow;
    } on Object {
      throw const AuthenticationFailure(AuthenticationFailureType.unavailable);
    }
  }

  @override
  Future<void> signOut() async {
    try {
      await _client.auth.signOut();
    } on Object {
      throw const AuthenticationFailure(AuthenticationFailureType.unavailable);
    }
  }

  domain.AuthSession? _mapSession(Session? session) {
    final user = session?.user;
    if (user == null) return null;
    return domain.AuthSession(userId: user.id, email: user.email);
  }
}

AuthenticationFailure mapSupabaseAuthException(AuthException error) {
  const rejectedCredentialCodes = {'invalid_credentials', 'user_not_found'};
  if (rejectedCredentialCodes.contains(error.code)) {
    return const AuthenticationFailure(
      AuthenticationFailureType.invalidCredentials,
    );
  }

  if (error.code == 'email_not_confirmed') {
    return const AuthenticationFailure(
      AuthenticationFailureType.emailNotConfirmed,
    );
  }

  final statusCode = int.tryParse(error.statusCode ?? '');
  if (error is AuthRetryableFetchException ||
      statusCode == 429 ||
      (statusCode != null && statusCode >= 500)) {
    return const AuthenticationFailure(AuthenticationFailureType.unavailable);
  }

  return const AuthenticationFailure(AuthenticationFailureType.unknown);
}
