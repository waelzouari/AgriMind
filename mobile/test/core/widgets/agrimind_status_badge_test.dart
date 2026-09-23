import 'package:agrimind/core/models/ui_status.dart';
import 'package:agrimind/core/widgets/agrimind_status_badge.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  for (final status in UiStatus.values) {
    testWidgets('$status has text, icon and semantics', (tester) async {
      await pumpAgriMindWidget(tester, AgriMindStatusBadge(status: status));

      expect(find.text(status.label), findsOneWidget);
      expect(find.byIcon(status.icon), findsOneWidget);
      expect(find.bySemanticsLabel('État : ${status.label}'), findsOneWidget);
    });
  }

  testWidgets('long custom status wraps without overflow', (tester) async {
    await pumpAgriMindWidget(
      tester,
      const AgriMindStatusBadge(
        status: UiStatus.stale,
        labelOverride: 'Données anciennes à vérifier sur le terrain',
      ),
      size: const Size(320, 568),
      textScaleFactor: 1.5,
    );

    expect(tester.takeException(), isNull);
  });
}
