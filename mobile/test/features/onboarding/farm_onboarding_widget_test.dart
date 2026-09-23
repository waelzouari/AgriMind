import 'dart:async';

import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/domain/auth_session.dart';
import 'package:agrimind/features/auth/presentation/authenticated_home_page.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/onboarding/domain/farm_failure.dart';
import 'package:agrimind/features/onboarding/presentation/farm_onboarding_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/auth_test_app.dart';
import '../../helpers/fake_authentication_repository.dart';
import '../../helpers/fake_farm_repository.dart';

void main() {
  const session = AuthSession(userId: 'user-a', email: 'farmer@example.com');

  testWidgets('authenticated startup waits for farm lookup', (tester) async {
    final authRepository = FakeAuthenticationRepository(
      restoredSession: session,
    );
    final farmRepository = FakeFarmRepository()
      ..lookupCompleter = Completer<Farm?>();

    await tester.pumpWidget(
      authTestApp(
        AuthenticationController(authRepository),
        farmRepository: farmRepository,
      ),
    );
    await tester.pump();

    expect(find.text('Vérification de votre ferme'), findsOneWidget);
    expect(find.byType(FarmOnboardingPage), findsNothing);
    farmRepository.lookupCompleter!.complete(null);
    await tester.pumpAndSettle();
    expect(find.byType(FarmOnboardingPage), findsOneWidget);
    await authRepository.close();
  });

  testWidgets('form validates, creates once, and enters configured home', (
    tester,
  ) async {
    final authRepository = FakeAuthenticationRepository(
      restoredSession: session,
    );
    final farmRepository = FakeFarmRepository();

    await tester.pumpWidget(
      authTestApp(
        AuthenticationController(authRepository),
        farmRepository: farmRepository,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Créer ma ferme'));
    await tester.pump();
    expect(find.text('Saisissez le nom de la ferme.'), findsOneWidget);
    expect(farmRepository.creationCalls, 0);

    await tester.enterText(find.byKey(const Key('farm-name')), '  Ferme Sud  ');
    await tester.tap(find.text('Créer ma ferme'));
    await tester.pumpAndSettle();
    expect(farmRepository.creationCalls, 1);
    expect(farmRepository.submittedName, 'Ferme Sud');
    expect(find.byType(AuthenticatedHomePage), findsOneWidget);
    expect(find.text('Ferme Sud'), findsOneWidget);
    await authRepository.close();
  });

  testWidgets('lookup failure shows retry instead of onboarding', (
    tester,
  ) async {
    final authRepository = FakeAuthenticationRepository(
      restoredSession: session,
    );
    final farmRepository = FakeFarmRepository()
      ..lookupError = const FarmFailure(FarmFailureType.unavailable);

    await tester.pumpWidget(
      authTestApp(
        AuthenticationController(authRepository),
        farmRepository: farmRepository,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Ferme indisponible'), findsOneWidget);
    expect(find.byType(FarmOnboardingPage), findsNothing);
    farmRepository
      ..lookupError = null
      ..currentFarm = const Farm(id: 'farm-a', name: 'Ferme retrouvée');
    await tester.tap(find.text('Réessayer'));
    await tester.pumpAndSettle();
    expect(find.text('Ferme retrouvée'), findsOneWidget);
    await authRepository.close();
  });

  testWidgets('onboarding remains usable on a narrow scaled viewport', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final authRepository = FakeAuthenticationRepository(
      restoredSession: session,
    );
    final farmRepository = FakeFarmRepository();

    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.3)),
        child: authTestApp(
          AuthenticationController(authRepository),
          farmRepository: farmRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Configurez votre ferme'), findsOneWidget);
    expect(find.text('Créer ma ferme'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await authRepository.close();
  });
}
