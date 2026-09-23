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
    } on AuthException {
      throw const AuthenticationFailure(
        AuthenticationFailureType.invalidCredentials,
      );
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
