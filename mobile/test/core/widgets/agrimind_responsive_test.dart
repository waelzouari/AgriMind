import 'package:agrimind/core/pages/foundation_showcase_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  for (final size in [
    const Size(320, 568),
    const Size(390, 844),
    const Size(600, 960),
  ]) {
    testWidgets('showcase has no overflow at $size', (tester) async {
      await pumpAgriMindWidget(
        tester,
        const FoundationShowcasePage(),
        size: size,
      );

      expect(find.text('Fondation visuelle'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('small screen supports increased text scaling and French copy', (
    tester,
  ) async {
    await pumpAgriMindWidget(
      tester,
      const FoundationShowcasePage(),
      size: const Size(320, 568),
      textScaleFactor: 1.5,
    );

    expect(
      find.textContaining('fonctionnalités seront ajoutées'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });
}
