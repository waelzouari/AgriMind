import 'package:agrimind/core/widgets/agrimind_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  testWidgets('enabled button invokes its callback and meets touch target', (
    tester,
  ) async {
    var taps = 0;
    await pumpAgriMindWidget(
      tester,
      AgriMindButton(label: 'Continuer', onPressed: () => taps++),
    );

    await tester.tap(find.text('Continuer'));

    expect(taps, 1);
    expect(
      tester.getSize(find.byType(ElevatedButton)).height,
      greaterThanOrEqualTo(48),
    );
    expect(find.bySemanticsLabel('Continuer'), findsOneWidget);
  });

  testWidgets('disabled button does not invoke its callback', (tester) async {
    await pumpAgriMindWidget(
      tester,
      const AgriMindButton(label: 'Indisponible', onPressed: null),
    );

    expect(
      tester.widget<ElevatedButton>(find.byType(ElevatedButton)).onPressed,
      isNull,
    );
  });

  testWidgets('loading button disables interaction and exposes its state', (
    tester,
  ) async {
    var taps = 0;
    await pumpAgriMindWidget(
      tester,
      AgriMindButton(
        label: 'Enregistrer',
        onPressed: () => taps++,
        loading: true,
      ),
    );

    await tester.tap(find.byType(ElevatedButton));

    expect(taps, 0);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.bySemanticsLabel('Enregistrer'), findsOneWidget);
  });
}
