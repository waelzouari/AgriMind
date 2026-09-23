import 'dart:async';

import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/domain/auth_session.dart';
import 'package:agrimind/features/auth/domain/authentication_failure.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_authentication_repository.dart';

void main() {
  const session = AuthSession(userId: 'user-a', email: 'farmer@example.com');

  test('restores no session as unauthenticated', () async {
    final repository = FakeAuthenticationRepository();
    final controller = AuthenticationController(repository);

    expect(controller.status, AuthenticationStatus.restoring);
    await controller.restoreSession();

    expect(controller.status, AuthenticationStatus.unauthenticated);
    expect(controller.session, isNull);
    await repository.close();
  });

  test('restores a valid persisted session as authenticated', () async {
    final repository = FakeAuthenticationRepository(restoredSession: session);
    final controller = AuthenticationController(repository);

    await controller.restoreSession();

    expect(controller.status, AuthenticationStatus.authenticated);
    expect(controller.session, session);
    await repository.close();
  });

  test('restoration failure fails closed without exposing exception', () async {
    final secret = 'token-must-not-appear'; // pragma: allowlist secret
    final repository = FakeAuthenticationRepository()
      ..restoreError = StateError(secret);
    final controller = AuthenticationController(repository);

    await controller.restoreSession();

    expect(controller.status, AuthenticationStatus.unauthenticated);
    expect(controller.errorMessage, isNot(contains(secret)));
    await repository.close();
  });

  test('sign-in succeeds and invalid credentials remain safe', () async {
    final repository = FakeAuthenticationRepository();
    final controller = AuthenticationController(repository);
    await controller.restoreSession();

    await controller.signIn(
      email: 'farmer@example.com',
      password: 'private', // pragma: allowlist secret
    );
    expect(controller.status, AuthenticationStatus.authenticated);

    repository.signInFailure = const AuthenticationFailure(
      AuthenticationFailureType.invalidCredentials,
    );
    await controller.signIn(
      email: 'farmer@example.com',
      password: 'wrong', // pragma: allowlist secret
    );
    expect(controller.status, AuthenticationStatus.unauthenticated);
    expect(controller.errorMessage, contains('incorrect'));
    expect(controller.errorMessage, isNot(contains('wrong')));
    await repository.close();
  });

  test('repeated submit while pending creates one request', () async {
    final repository = FakeAuthenticationRepository()
      ..signInCompleter = Completer<AuthSession>();
    final controller = AuthenticationController(repository);
    await controller.restoreSession();

    final first = controller.signIn(
      email: 'farmer@example.com',
      password: 'private', // pragma: allowlist secret
    );
    final second = controller.signIn(
      email: 'farmer@example.com',
      password: 'private', // pragma: allowlist secret
    );
    expect(repository.signInCalls, 1);
    repository.signInCompleter!.complete(session);
    await Future.wait([first, second]);

    expect(controller.status, AuthenticationStatus.authenticated);
    await repository.close();
  });

  test('sign-out and external auth changes update state immediately', () async {
    final repository = FakeAuthenticationRepository(restoredSession: session);
    final controller = AuthenticationController(repository);
    await controller.restoreSession();

    repository.emit(null);
    expect(controller.status, AuthenticationStatus.unauthenticated);
    repository.emit(session);
    expect(controller.status, AuthenticationStatus.authenticated);
    await controller.signOut();
    expect(controller.status, AuthenticationStatus.unauthenticated);
    expect(repository.signOutCalls, 1);
    await repository.close();
  });
}
