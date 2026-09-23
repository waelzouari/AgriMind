import 'package:agrimind/core/models/ui_status.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  testWidgets('presents a metric and text-supported status responsively', (
    tester,
  ) async {
    await pumpAgriMindWidget(
      tester,
      const AgriMindMetricCard(
        icon: Icons.water_drop_outlined,
        label: 'Humidité du sol',
        value: '64',
        unit: '%',
        status: AgriMindStatusBadge(
          status: UiStatus.success,
          labelOverride: 'Optimal',
        ),
      ),
      size: const Size(320, 568),
      textScaleFactor: 1.5,
    );

    expect(find.text('Humidité du sol'), findsOneWidget);
    expect(find.text('64'), findsOneWidget);
    expect(find.text('Optimal'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
