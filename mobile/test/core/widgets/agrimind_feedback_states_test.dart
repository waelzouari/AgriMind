import 'package:agrimind/core/widgets/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  testWidgets('loading state includes an accessible label', (tester) async {
    await pumpAgriMindWidget(
      tester,
      const AgriMindLoadingIndicator(label: 'Préparation en cours'),
    );

    expect(find.bySemanticsLabel('Préparation en cours'), findsOneWidget);
  });

  testWidgets('empty state communicates title and detail', (tester) async {
    await pumpAgriMindWidget(
      tester,
      const AgriMindEmptyState(
        title: 'Aucune donnée',
        message: 'Les données disponibles apparaîtront ici.',
      ),
    );

    expect(find.text('Aucune donnée'), findsOneWidget);
    expect(
      find.text('Les données disponibles apparaîtront ici.'),
      findsOneWidget,
    );
  });

  testWidgets('error retry invokes recovery once', (tester) async {
    var retries = 0;
    await pumpAgriMindWidget(
      tester,
      AgriMindErrorState(
        title: 'Impossible de continuer',
        message: 'Vérifiez la situation puis réessayez.',
        onRetry: () => retries++,
      ),
    );

    expect(find.bySemanticsLabel('Réessayer'), findsOneWidget);
    await tester.tap(find.bySemanticsLabel('Réessayer'));

    expect(retries, 1);
  });
}
