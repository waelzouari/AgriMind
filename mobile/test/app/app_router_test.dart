import 'package:agrimind/app/agrimind_app.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('unknown routes show an explicit accessible error', (
    tester,
  ) async {
    await tester.pumpWidget(const AgriMindApp(config: AppConfig()));

    Navigator.of(
      tester.element(find.byType(Scaffold).first),
    ).pushNamed('/unknown');
    await tester.pumpAndSettle();

    expect(find.text('Page introuvable'), findsOneWidget);
    expect(find.text('Route inconnue'), findsOneWidget);
    expect(find.textContaining('/unknown'), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Route inconnue')), findsOneWidget);
  });
}
