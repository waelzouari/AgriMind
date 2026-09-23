import 'package:agrimind/core/assets/agrimind_assets.dart';
import 'package:agrimind/core/widgets/agrimind_logo.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  testWidgets('renders the official asset with accessible branding', (
    tester,
  ) async {
    await pumpAgriMindWidget(tester, const AgriMindLogo());

    final image = tester.widget<Image>(find.byType(Image));
    expect((image.image as AssetImage).assetName, AgriMindAssets.logo);
    expect(find.bySemanticsLabel('AgriMind'), findsOneWidget);
  });
}
