import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/auth_test_app.dart';
import '../helpers/fake_authentication_repository.dart';

void main() {
  testWidgets('unknown routes show an explicit accessible error', (
    tester,
  ) async {
    final repository = FakeAuthenticationRepository();
    await tester.pumpWidget(authTestApp(AuthenticationController(repository)));
    await tester.pumpAndSettle();

    Navigator.of(
      tester.element(find.byType(Scaffold).first),
    ).pushNamed('/unknown');
    await tester.pumpAndSettle();

    expect(find.text('Page introuvable'), findsOneWidget);
    expect(find.text('Route inconnue'), findsOneWidget);
    expect(find.textContaining('/unknown'), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Route inconnue')), findsOneWidget);
    await repository.close();
  });
}
