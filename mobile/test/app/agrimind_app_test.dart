import 'dart:async';

import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/domain/auth_session.dart';
import 'package:agrimind/features/auth/domain/authentication_failure.dart';
import 'package:agrimind/features/auth/presentation/authenticated_home_page.dart';
import 'package:agrimind/features/auth/presentation/sign_in_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/auth_test_app.dart';
import '../helpers/fake_authentication_repository.dart';

void main() {
  const session = AuthSession(userId: 'user-a', email: 'farmer@example.com');

  testWidgets('keeps the restoration screen visible until startup completes', (
    tester,
  ) async {
    final repository = FakeAuthenticationRepository()
      ..restoreCompleter = Completer<AuthSession?>();
    final controller = AuthenticationController(repository);

    await tester.pumpWidget(authTestApp(controller));
    await tester.pump();

    expect(find.text('Restauration de la session'), findsOneWidget);
    expect(find.byType(SignInPage), findsNothing);
    repository.restoreCompleter!.complete(null);
    await tester.pumpAndSettle();
    expect(find.byType(SignInPage), findsOneWidget);
    await repository.close();
  });

  testWidgets('restores a persisted session without showing sign-in', (
    tester,
  ) async {
    final repository = FakeAuthenticationRepository(restoredSession: session);

    await tester.pumpWidget(authTestApp(AuthenticationController(repository)));
    await tester.pumpAndSettle();

    expect(find.byType(AuthenticatedHomePage), findsOneWidget);
    expect(find.byType(SignInPage), findsNothing);
    await repository.close();
  });

  testWidgets('validates locally and displays a secret-safe auth error', (
    tester,
  ) async {
    final repository = FakeAuthenticationRepository();
    final controller = AuthenticationController(repository);
    await tester.pumpWidget(authTestApp(controller));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('sign-in-email')), 'invalid');
    await tester.enterText(find.byKey(const Key('sign-in-password')), 'secret');
    await tester.tap(find.text('Se connecter'));
    await tester.pump();
    expect(find.text('Saisissez une adresse e-mail valide.'), findsOneWidget);
    expect(repository.signInCalls, 0);

    repository.signInFailure = const AuthenticationFailure(
      AuthenticationFailureType.invalidCredentials,
    );
    await tester.enterText(
      find.byKey(const Key('sign-in-email')),
      'farmer@example.com',
    );
    await tester.tap(find.text('Se connecter'));
    await tester.pumpAndSettle();
    final error = tester.widget<Text>(find.byKey(const Key('sign-in-error')));
    expect(error.data, isNotNull);
    expect(find.textContaining('incorrect'), findsOneWidget);
    expect(error.data, isNot(contains('secret')));
    await repository.close();
  });

  testWidgets('signs out and keeps protected routes behind the auth gate', (
    tester,
  ) async {
    final repository = FakeAuthenticationRepository(restoredSession: session);
    final controller = AuthenticationController(repository);
    await tester.pumpWidget(authTestApp(controller));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Se déconnecter'));
    await tester.pumpAndSettle();
    expect(find.byType(SignInPage), findsOneWidget);

    Navigator.of(tester.element(find.byType(SignInPage))).pushNamed('/home');
    await tester.pumpAndSettle();
    expect(find.byType(SignInPage), findsWidgets);
    expect(find.byType(AuthenticatedHomePage), findsNothing);
    await repository.close();
  });
}
