import 'dart:async';

import 'package:agrimind/features/auth/application/authentication_repository.dart';
import 'package:agrimind/features/auth/domain/auth_session.dart';
import 'package:agrimind/features/auth/domain/authentication_failure.dart';

final class FakeAuthenticationRepository implements AuthenticationRepository {
  FakeAuthenticationRepository({this.restoredSession});

  final _changes = StreamController<AuthSession?>.broadcast(sync: true);
  AuthSession? restoredSession;
  Object? restoreError;
  Completer<AuthSession?>? restoreCompleter;
  AuthSession signInResult = const AuthSession(
    userId: 'user-a',
    email: 'farmer@example.com',
  );
  AuthenticationFailure? signInFailure;
  Completer<AuthSession>? signInCompleter;
  int restoreCalls = 0;
  int signInCalls = 0;
  int signOutCalls = 0;

  @override
  Stream<AuthSession?> get authStateChanges => _changes.stream;

  @override
  Future<AuthSession?> restoreSession() async {
    restoreCalls += 1;
    if (restoreError case final error?) throw error;
    return restoreCompleter?.future ?? restoredSession;
  }

  @override
  Future<AuthSession> signIn({
    required String email,
    required String password,
  }) async {
    signInCalls += 1;
    if (signInFailure case final failure?) throw failure;
    return signInCompleter?.future ?? signInResult;
  }

  @override
  Future<void> signOut() async {
    signOutCalls += 1;
  }

  void emit(AuthSession? session) => _changes.add(session);

  Future<void> close() => _changes.close();
}
