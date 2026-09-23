import 'package:agrimind/app/agrimind_app.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/core/pages/foundation_showcase_page.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('starts on the technical foundation showcase', (tester) async {
    await tester.pumpWidget(const AgriMindApp(config: AppConfig()));

    expect(find.text('AGRIMIND'), findsOneWidget);
    expect(find.byType(FoundationShowcasePage), findsOneWidget);
    expect(find.text('Fondation visuelle'), findsOneWidget);
    expect(find.textContaining('Aucune donnée agricole'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
